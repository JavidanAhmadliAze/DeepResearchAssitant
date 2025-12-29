from fastapi import APIRouter, Depends
from backend.db import get_async_session
from sqlalchemy.ext.asyncio import AsyncSession
from backend.db import User
from backend.models.schemas import ChatHistoryItem
from typing_extensions import List
from backend.routers.users import current_active_user
from backend.db import ResearchTask
from sqlalchemy import select, desc

router = APIRouter(prefix='/history', tags=['history'])

@router.get("/", response_model=List[ChatHistoryItem])
async def get_list(
    db: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_active_user),
    limit: int = 50,  # Optional query parameter
    offset: int = 0   # For pagination
):
    query = (
        select(ResearchTask)
        .where(ResearchTask.user_id == user.id)
        .order_by(desc(ResearchTask.updated_at))  # Most recent first
        .limit(limit)
        .offset(offset)
    )
    result = await db.execute(query)
    tasks = result.scalars().all()

    return [
        ChatHistoryItem(
            chat_id=task.thread_id,
            title=task.initial_query[:50] + ("..." if len(task.initial_query) > 50 else ""),
            last_updated=task.updated_at,
        ) for task in tasks
    ]