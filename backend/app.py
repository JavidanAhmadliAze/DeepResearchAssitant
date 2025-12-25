from fastapi import FastAPI
from backend.routers.users import auth_backend, fastapi_users
from backend.models.schemas import UserCreate, UserRead, UserUpdate
from contextlib import asynccontextmanager
from backend.db import create_db_and_tables
from routers.chat import router as chat_router


@asynccontextmanager
async def lifespan():
    await create_db_and_tables()
    yield

app = FastAPI(lifespan=lifespan)


app.include_router(fastapi_users.get_auth_router(auth_backend), prefix='/auth/jwt', tags=["auth"])
app.include_router(fastapi_users.get_register_router(UserRead, UserCreate), prefix="/auth", tags=["auth"])
app.include_router(fastapi_users.get_reset_password_router(), prefix="/auth", tags=["auth"])
app.include_router(fastapi_users.get_verify_router(UserRead), prefix="/auth", tags=["auth"])
app.include_router(fastapi_users.get_users_router(UserRead, UserUpdate), prefix="/users", tags=["users"])

app.include_router(chat_router)
