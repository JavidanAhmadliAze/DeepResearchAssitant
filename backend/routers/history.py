import uuid

from fastapi import APIRouter, Depends
from backend.db import get_async_session
from sqlalchemy.ext.asyncio import AsyncSession
from backend.db import User
from backend.models.schemas import ChatHistoryItem
from typing_extensions import List
from backend.routers.users import current_active_user
from backend.db import ResearchTask
from sqlalchemy import select
from src.agents.workflow_executor import connection_pool
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

router = APIRouter(prefix='/history', tags=['history'])

@router.get("/", response_model=List[ChatHistoryItem])
async def get_list(
        db: AsyncSession = Depends(get_async_session),
        user: User = Depends(current_active_user)
):

    query = select(ResearchTask).where(ResearchTask.user_id==user.id)
    result  = await db.execute(query)
    tasks = result.scalars().all()

    return [
        ChatHistoryItem(
            chat_id=task.thread_id,
            title=task.initial_query[:50],
            last_updated=task.created_at
        ) for task in tasks]
