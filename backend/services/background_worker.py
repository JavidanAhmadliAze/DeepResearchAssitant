import logging
import uuid
import datetime
from src.agents.workflow_executor import connection_pool, deep_researcher_builder
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from backend.db import get_async_session_context, ResearchTask, TaskStatus
from langchain_core.messages import HumanMessage
from sqlalchemy import update
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from langchain_chroma import Chroma
from langchain_core.documents import Document

logger = logging.getLogger(__name__)


async def run_agent_workflow(chat_id: str, user_query: str, user_id: uuid.UUID):
    thread_id = chat_id

    async with get_async_session_context() as db:
        try:
            async with connection_pool.connection() as conn:
                checkpointer = AsyncPostgresSaver(conn)
                # No need to run setup() every time, but it's safe if you do

                # Use the global builder to compile the agent
                agent = deep_researcher_builder.compile(checkpointer=checkpointer)

                config = {"configurable": {
                    "thread_id": thread_id,
                    "user_id": user_id
                }}

                # --- CRITICAL CHANGE ---
                # We pass None because the 'user_query' is already in the Postgres checkpoint
                # from the POST request. Passing it again creates a duplicate message.
                # Passing None tells LangGraph to "Resume the current thread".
                final_state = await agent.ainvoke(None, config=config)

                # Update status to SUMMARIZING now that heavy research is done
                stmt_summarizing = (
                    update(ResearchTask)
                    .where(ResearchTask.thread_id == thread_id)
                    .values(status=TaskStatus.SUMMARIZING)
                )
                await db.execute(stmt_summarizing)
                await db.commit()

                final_text = final_state.get("final_report", "")

                # Only proceed if we actually got a report
                if final_text:
                    # 1. Prepare Document for Vector Store
                    doc = Document(
                        page_content=final_text,
                        metadata={
                            "user_query": user_query,
                            "timestamp": datetime.datetime.now(),
                            "type": "final_report",
                            "chat_id": chat_id
                        }
                    )

                    # 2. Vector DB Logic
                    embedding = GoogleGenerativeAIEmbeddings(model="gemini-embedding-001")
                    VECTOR_DB_PATH = "./data/output"
                    chroma_db = Chroma(
                        collection_name="deep_research_texts",
                        embedding_function=embedding,
                        persist_directory=VECTOR_DB_PATH
                    )

                    text_splitter = RecursiveCharacterTextSplitter(
                        chunk_size=1800,
                        chunk_overlap=200
                    )
                    all_splits = text_splitter.split_documents([doc])
                    chroma_db.add_documents(all_splits)

                # 3. Final Status Update
                stmt_complete = (
                    update(ResearchTask)
                    .where(ResearchTask.thread_id == thread_id)
                    .values(status=TaskStatus.COMPLETED)
                )
                await db.execute(stmt_complete)
                await db.commit()
                print(f"✅ Research completed for thread: {thread_id}", flush=True)

        except Exception as e:
            logger.error(f"Workflow error: {e}")
            stmt_failed = (
                update(ResearchTask)
                .where(ResearchTask.thread_id == thread_id)
                .values(status=TaskStatus.FAILED)
            )
            await db.execute(stmt_failed)
            await db.commit()