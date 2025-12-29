import uuid
import enum
from datetime import datetime
from typing import List, Optional
from fastapi import Depends
import contextlib

from sqlalchemy import String, Text, ForeignKey, Enum, Integer, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.types import Uuid
from fastapi_users.db import SQLAlchemyUserDatabase, SQLAlchemyBaseUserTableUUID
import os

DATABASE_URL = os.getenv("ASYNC_DATABASE_URL")

class Base(DeclarativeBase):
    pass


class User(SQLAlchemyBaseUserTableUUID, Base):
    __tablename__ = "users"
    tasks: Mapped[List["ResearchTask"]] = relationship(back_populates="user")


class TaskStatus(enum.Enum):
    CLARIFYING = "Clarifying"
    SEARCHING = "Searching"
    SUMMARIZING = "Summarizing"
    COMPLETED = "Completed"
    FAILED = "Failed"


class ResearchTask(Base):
    __tablename__ = "research_tasks"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    thread_id: Mapped[str] = mapped_column(String, unique=True, index=True)

    initial_query: Mapped[str] = mapped_column(Text)
    research_brief: Mapped[Optional[str]] = mapped_column(Text)
    final_report: Mapped[Optional[str]] = mapped_column(Text)
    status: Mapped[TaskStatus] = mapped_column(
        Enum(TaskStatus, name="task_status_enum"),
        default=TaskStatus.CLARIFYING
    )
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(default=datetime.utcnow, onupdate=datetime.utcnow)

    user: Mapped["User"] = relationship(back_populates="tasks")

engine = create_async_engine(DATABASE_URL)
async_session_maker = async_sessionmaker(engine, expire_on_commit=False)


async def create_db_and_tables():
    async with engine.begin() as conn:
        # Use Base.metadata so it sees all classes
        await conn.run_sync(Base.metadata.create_all)

async def get_async_session():
    async with async_session_maker() as session:
        yield session

async def get_user_db(session: AsyncSession = Depends(get_async_session)):
    yield SQLAlchemyUserDatabase(session, User)

get_async_session_context = contextlib.asynccontextmanager(get_async_session)