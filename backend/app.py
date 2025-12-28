from fastapi import FastAPI
from backend.routers.users import auth_backend, fastapi_users
from backend.models.schemas import UserCreate, UserRead, UserUpdate
from contextlib import asynccontextmanager
from backend.db import create_db_and_tables
from backend.routers.chat import router as chat_router
from backend.routers.history import router as history_router

from contextlib import asynccontextmanager
from fastapi import FastAPI
from backend.db import create_db_and_tables
# Import your pool and saver
from src.agents.workflow_executor import connection_pool
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 1. Create standard SQLAlchemy tables (Users, Tasks, etc.)
    await create_db_and_tables()

    # 2. Setup LangGraph Checkpointer tables (checkpoints, writes)
    # We open a connection from the pool specifically for setup
    async with connection_pool.connection() as conn:
        # Crucial: This avoids the "CREATE INDEX CONCURRENTLY" error
        await conn.set_autocommit(True)

        checkpointer = AsyncPostgresSaver(conn)
        await checkpointer.setup()

        print("✅ LangGraph checkpoint tables are ready.")

        # Set it back to False for safety if the pool is reused
        await conn.set_autocommit(False)

    yield
    # Cleanup logic (if needed) goes here

app = FastAPI(lifespan=lifespan)


app.include_router(fastapi_users.get_auth_router(auth_backend), prefix='/auth/jwt', tags=["auth"])
app.include_router(fastapi_users.get_register_router(UserRead, UserCreate), prefix="/auth", tags=["auth"])
app.include_router(fastapi_users.get_reset_password_router(), prefix="/auth", tags=["auth"])
app.include_router(fastapi_users.get_verify_router(UserRead), prefix="/auth", tags=["auth"])
app.include_router(fastapi_users.get_users_router(UserRead, UserUpdate), prefix="/users", tags=["users"])

app.include_router(chat_router)
app.include_router(history_router)

