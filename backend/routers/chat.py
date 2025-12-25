from fastapi import FastAPI, APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from backend.db import get_async_session
from backend.models.schemas import ChatResponse, ChatRequest
from backend.db import User
from backend.routers.users import current_active_user
from src.agents.workflow_executor import agent
from langchain_core.messages import HumanMessage



router = APIRouter(prefix='/chat', tags=['chat'])

@router.post('/ask', response_model=ChatResponse)
async def handle_agent_chat(
        payload: ChatRequest,
        db: AsyncSession = Depends(get_async_session),
        user: User = Depends(current_active_user)
):
    thread_id = str(payload.chat_id)

    config = {
        "configurable" : {
            "thread_id": thread_id,
            "db_session": db,
            "user_id": user.id
        }
    }
    try:
        final_message = agent.ainvoke([HumanMessage(content=payload.text)],config=config)
        return ChatResponse(chat_id=payload.chat_id,messages=final_message)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Agent Error {str(e)}")










