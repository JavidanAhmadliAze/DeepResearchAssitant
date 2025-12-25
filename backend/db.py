import uuid
import enum
from datetime import datetime
from typing import List, Optional
from fastapi import Depends

from sqlalchemy import String, Text, ForeignKey, Enum, Integer, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.types import Uuid
from fastapi_users.db import SQLAlchemyUserDatabase, SQLAlchemyBaseUserTableUUID

DATABASE_URL = "postgresql+asyncpg://user:password@localhost/dbname"

class Base(DeclarativeBase):
    pass


class User(SQLAlchemyBaseUserTableUUID, Base):

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

    brief: Mapped["ResearchBrief"] = relationship(back_populates="task", uselist=False)
    thoughts: Mapped[List["SupervisorThought"]] = relationship(back_populates="task")
    subtasks: Mapped[List["ResearchSubtask"]] = relationship(back_populates="task")


class ResearchBrief(Base):
    __tablename__ = "research_briefs"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    task_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("research_tasks.id"))
    finalized_question: Mapped[str] = mapped_column(Text)
    scope_constraints: Mapped[Optional[str]] = mapped_column(Text)

    task: Mapped["ResearchTask"] = relationship(back_populates="brief")


class SupervisorThought(Base):
    __tablename__ = "supervisor_thoughts"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    task_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("research_tasks.id"))
    iteration: Mapped[int] = mapped_column(Integer)
    thought_process: Mapped[str] = mapped_column(Text)

    task: Mapped["ResearchTask"] = relationship(back_populates="thoughts")


class ResearchSubtask(Base):
    __tablename__ = "research_subtasks"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    task_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("research_tasks.id"))
    topic: Mapped[str] = mapped_column(String)
    status: Mapped[str] = mapped_column(String, default="pending")

    task: Mapped["ResearchTask"] = relationship(back_populates="subtasks")
    sources: Mapped[List["Source"]] = relationship(back_populates="subtask")


class Source(Base):
    __tablename__ = "sources"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    subtask_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("research_subtasks.id"))
    url: Mapped[str] = mapped_column(String)
    title: Mapped[Optional[str]] = mapped_column(String)

    subtask: Mapped["ResearchSubtask"] = relationship(back_populates="sources")
    findings: Mapped[List["Finding"]] = relationship(back_populates="source")


class Finding(Base):
    __tablename__ = "findings"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    source_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("sources.id"))
    content: Mapped[str] = mapped_column(Text)

    source: Mapped["Source"] = relationship(back_populates="findings")
    citations: Mapped[List["ReportCitation"]] = relationship(back_populates="finding")


class ReportCitation(Base):
    __tablename__ = "report_citations"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    task_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("research_tasks.id"))
    finding_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("findings.id"))
    citation_index: Mapped[int] = mapped_column(Integer)

    finding: Mapped["Finding"] = relationship(back_populates="citations")


class Evaluation(Base):
    """Stores automated or human-led assessments of a specific task."""
    __tablename__ = "evaluations"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    task_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("research_tasks.id"))


    # Metrics
    relevance_score: Mapped[float] = mapped_column(nullable=True)  # 0.0 - 1.0
    groundedness_score: Mapped[float] = mapped_column(nullable=True)  # No hallucinations
    completeness_score: Mapped[float] = mapped_column(nullable=True)  # Did it answer all parts?

    llm_judge_feedback: Mapped[Optional[str]] = mapped_column(Text)
    human_rating: Mapped[Optional[int]] = mapped_column(Integer)  # e.g., 1-5 stars

    task: Mapped["ResearchTask"] = relationship()


class AgentMetrics(Base):
    """Tracks the 'cost of thinking' for each task."""
    __tablename__ = "agent_metrics"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    task_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("research_tasks.id"))
    agent_name: Mapped[str] = mapped_column(String, index=True)

    prompt_tokens: Mapped[int] = mapped_column(default=0)
    completion_tokens: Mapped[int] = mapped_column(default=0)
    total_cost: Mapped[float] = mapped_column(default=0.0)  # Calculated USD
    total_latency_ms: Mapped[int] = mapped_column(default=0)  # Time to complete

    tool_calls_count: Mapped[int] = mapped_column(default=0)  # Number of searches performed

engine = create_async_engine(DATABASE_URL)
async_session_maker = async_sessionmaker(engine, expire_on_commit=False)


async def create_db_and_tables():
    async with engine.begin() as conn:
        # Use Base.metadata so it sees all classes
        await conn.run_sync(Base.metadata.create_all)

async def get_async_session():
    async with async_session_maker as session:
        yield session

async def get_user_db(session: AsyncSession = Depends(get_async_session)):
    yield SQLAlchemyUserDatabase(session, User)