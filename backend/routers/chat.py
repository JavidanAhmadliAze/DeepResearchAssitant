import uuid
import datetime
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from backend.services.background_worker import run_agent_workflow
from src.agents.workflow_executor import connection_pool
from src.agents.scope_agent import scope_graph
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, status
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession
from backend.db import get_async_session, TaskStatus
from backend.models.schemas import ChatResponse, ChatRequest
from backend.db import User, ResearchTask
from backend.routers.users import current_active_user
from langchain_core.messages import HumanMessage
from sqlalchemy import select, update
from dotenv import load_dotenv
load_dotenv()
import logging
logger = logging.getLogger(__name__)


router = APIRouter(prefix="/chat",tags=['chat'])


@router.post("/{chat_id}/messages", response_model=ChatResponse)
async def handle_agent_chat(
        chat_id: str,
        payload: ChatRequest,
        background_tasks: BackgroundTasks,
        db: AsyncSession = Depends(get_async_session),
        user: User = Depends(current_active_user)):

    query = select(ResearchTask).where(ResearchTask.thread_id==chat_id)
    result = await db.execute(query)
    task = result.scalar_one_or_none()

    if not task:
        task=ResearchTask(
        id=uuid.uuid4(),
        thread_id=chat_id,
        user_id=user.id,
        initial_query=payload.text,
        status=TaskStatus.CLARIFYING
        )
        db.add(task)
        await db.commit()

    else:
        await db.execute(
            update(ResearchTask)
            .where(ResearchTask.thread_id == chat_id)
            .values(updated_at=datetime.datetime.utcnow())
        )
        await db.commit()

    async with connection_pool.connection() as conn:

        checkpoint = AsyncPostgresSaver(conn)
        await checkpoint.setup()

        agent = scope_graph.compile(checkpointer=checkpoint)
        config = {"configurable": {"thread_id": chat_id, "user_id":user.id}}

        # Step 1: Execute the first node (Scoping/Retrieval)
        result = await agent.ainvoke({"messages": [HumanMessage(content=payload.text)]}, config=config)
        research_brief = result.get("research_brief", "")

        # Step 2: Format the conversation for the response
        messages = result.get("messages", [])
        formatted_messages = [
            {"role": "user" if m.type == "human" else "assistant", "content": m.content}
            for m in messages
        ]
        if research_brief:
            await db.execute(
                update(ResearchTask)
                .where(ResearchTask.thread_id == chat_id)
                .values(status=TaskStatus.SEARCHING)
            )
            await db.commit()
            # Start the background worker ONCE
            background_tasks.add_task(run_agent_workflow, chat_id, research_brief, user.id)
            return JSONResponse(
                status_code=status.HTTP_202_ACCEPTED,
                content={
                    "chat_id": chat_id,
                    "messages": formatted_messages,
                    "status": "research_started",
                    "message": "Research started in background. Poll /status for updates.",
                    "poll_url": f"/chat/{chat_id}"
                }
            )
    return ChatResponse(
        chat_id=chat_id,
        messages=formatted_messages,
    )

from psycopg.rows import dict_row
@router.get("/{chat_id}", response_model=ChatResponse)
async def get_chat(
        chat_id: str,
        db: AsyncSession = Depends(get_async_session),
        user: User = Depends(current_active_user)
):

    query = select(ResearchTask).where(
        ResearchTask.thread_id == chat_id,
        ResearchTask.user_id==user.id
    )

    result = await db.execute(query)
    task = result.scalar_one_or_none()
    final_text = task.final_report
    if not task:
        raise HTTPException(status_code=403, detail=f"Unable to load conversation {chat_id}")
    formatted_messages = []
    async with connection_pool.connection() as conn:
        conn.row_factory = dict_row
        checkpointer = AsyncPostgresSaver(conn)
        checkpoint = await checkpointer.aget_tuple(config={
        "configurable":{
            "thread_id": chat_id}
        })
        if checkpoint:
            # The actual data is usually inside checkpoint[1]['channel_values']
            # We use .get() to handle both flat and nested structures safely
            state = checkpoint[1]
            data = state.get("channel_values", state)

            # 1. Get Conversation Messages
            messages = data.get("messages", [])
            for msg in messages:
                role = "user" if msg.type == "human" else "assistant"
                formatted_messages.append({"role": role, "content": msg.content})

            return ChatResponse(
                chat_id=chat_id,
                messages=formatted_messages
            )
    if task.final_report:
        # Avoid duplicate entries if it's already in formatted_messages
        if not formatted_messages or formatted_messages[-1]["content"] != task.final_report:
            formatted_messages.append({
                "role": "assistant",
                "content": task.final_report
            })

    return ChatResponse(chat_id=chat_id, messages=[])

@router.delete('/{chat_id}')
async def delete_chat(
        chat_id: str,
        db: AsyncSession = Depends(get_async_session),
        user: User = Depends(current_active_user)
):
    try:
        result = await db.execute(select(ResearchTask).where(
            ResearchTask.thread_id == chat_id,
            ResearchTask.user_id == user.id
        ))
        chat = result.scalars().first()
        if not chat:
            raise HTTPException(status_code=404, detail="Chat not found")
        await db.delete(chat)
        await db.commit()

        return {"success": True, "message": "Chat deleted successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))