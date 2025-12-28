from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from backend.services.background_worker import run_agent_workflow
from src.agents.workflow_executor import connection_pool, deep_researcher_builder
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from backend.db import get_async_session, TaskStatus
from backend.models.schemas import ChatResponse, ChatRequest
from backend.db import User, ResearchTask
from backend.routers.users import current_active_user
from langchain_core.messages import HumanMessage
from sqlalchemy import select, update
from dotenv import load_dotenv
load_dotenv()


router = APIRouter(prefix="/chat",tags=['chat'])


@router.post("/{chat_id}/messages", response_model=ChatResponse)
async def handle_agent_chat(
        chat_id: str,
        payload: ChatRequest,
        background_tasks: BackgroundTasks,
        db: AsyncSession = Depends(get_async_session),
        user: User = Depends(current_active_user)):

    async with connection_pool.connection() as conn:
        checkpointer = AsyncPostgresSaver(conn)
        agent = deep_researcher_builder.compile(checkpointer=checkpointer)
        config = {"configurable": {"thread_id": chat_id, "user_id": user.id}}

        # Step 1: Execute the first node (Scoping/Retrieval)
        result = await agent.ainvoke({"messages": [HumanMessage(content=payload.text)]}, config=config)

    # Step 2: Format the conversation for the response
    messages = result.get("messages", [])
    formatted_messages = [
        {"role": "user" if m.type == "human" else "assistant", "content": m.content}
        for m in messages
    ]

    # Step 3: Check if we need to hand off to the Background Worker
    if result.get("trigger_search"):
        # Update SQL status so the GET poller sees "SEARCHING"
        await db.execute(
            update(ResearchTask)
            .where(ResearchTask.thread_id == chat_id)
            .values(status=TaskStatus.SEARCHING)
        )
        await db.commit()

        # Start the background worker ONCE
        background_tasks.add_task(run_agent_workflow, chat_id, payload.text, user.id)

    # Step 4: Return the current state (Clarification or "I'm starting research")
    return ChatResponse(chat_id=chat_id, messages=formatted_messages)

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

    if not task:
        raise HTTPException(status_code=403, detail=f"Unable to load conversation {chat_id}")

    async with connection_pool.connection() as conn:
        checkpointer = AsyncPostgresSaver(conn)
        await checkpointer.setup()
        state = await checkpointer.aget(config={
        "configurable":{
            "thread_id": chat_id,
        }
        })

        if state and "messages" in state.values():
            formatted_messages = [
                {"role": "user" if m.type == "human" else "assistant", "content": m.content}
                for m in state.values["messages"]
            ]
            return ChatResponse(
                chat_id=chat_id,
                messages=formatted_messages
            )

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