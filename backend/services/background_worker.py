import logging
import os
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
from src.agent_interface.states import SupervisorState
from src.agents.supervisor_agent import supervisor_builder
from langgraph.checkpoint.memory import InMemorySaver
from pathlib import Path
logger = logging.getLogger(__name__)


async def run_agent_workflow(chat_id: str, research_brief: str, user_id: uuid.UUID):
    thread_id = chat_id
    print(f"!!! DEBUG: Background task triggered for {chat_id} !!!", flush=True)
    logger.info("Background task is started")
    logger.info(f"chat_id: {chat_id}")
    logger.info(f"research brief: {research_brief}")
    logger.warning(f"🔥 Background task STARTED for chat_id={chat_id}, user_id={user_id}")

    supervisor_state = SupervisorState(
        supervisor_messages=[HumanMessage(content=f"{research_brief}.")],
        research_brief =  research_brief,
        notes=[],
        raw_notes=[],
        trigger_search=True,
        research_iterations=0
    )


    async with get_async_session_context() as db:
        try:
            async with connection_pool.connection() as conn:
                checkpoint = AsyncPostgresSaver(conn)
                await checkpoint.setup()

                # Using the global builder to compile the agent
                agent = deep_researcher_builder.compile(checkpointer=checkpoint)

                config = {"configurable": {
                    "thread_id": thread_id,
                    "user_id": user_id

                },"recursion_limit" : 100}
                await agent.aupdate_state(config, {
                    "research_brief": research_brief,
                    "trigger_search": True,
                    "research_iterations": 0,
                    "notes": [],
                    "raw_notes": []
                })

                final_state = await agent.ainvoke(None,config)

                # Update status to SUMMARIZING now that heavy research is done
                stmt_summarizing = (
                    update(ResearchTask)
                    .where(ResearchTask.thread_id == thread_id)
                    .values(status=TaskStatus.SUMMARIZING)
                )
                await db.execute(stmt_summarizing)
                await db.commit()

                final_text = final_state.get("final_report", "")
                need_search = final_state.get("trigger_search", False)

                # Only proceed if we actually got a report
                if final_text and need_search:
                    # 1. Prepare Document for Vector Store
                    doc = Document(
                        page_content=final_text,
                        metadata={
                            "research_brief": research_brief,
                            "timestamp": datetime.datetime.now().isoformat(),
                            "type": "final_report",
                            "chat_id": chat_id
                        }
                    )

                    # 2. Vector DB Logic
                    embedding = GoogleGenerativeAIEmbeddings(model="gemini-embedding-001")
                    VECTOR_DB_PATH = Path(r"C:\Users\User\PythonProject\data\output").resolve()
                    os.makedirs(VECTOR_DB_PATH, exist_ok=True)
                    chroma_db = Chroma(
                        collection_name="deep_research_texts",
                        embedding_function=embedding,
                        persist_directory=str(VECTOR_DB_PATH)
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
                    .values(final_report=final_text,status=TaskStatus.COMPLETED)
                )
                await db.execute(stmt_complete)
                await db.commit()
                print(f"Research completed for thread: {thread_id}", flush=True)

        except Exception as e:
            logger.error(f"Workflow error: {e}")
            stmt_failed = (
                update(ResearchTask)
                .where(ResearchTask.thread_id == thread_id)
                .values(status=TaskStatus.FAILED)
            )
            await db.execute(stmt_failed)
            await db.commit()