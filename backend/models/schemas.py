from pydantic import BaseModel, Field
from typing_extensions import Optional, List
from fastapi_users import schemas
from datetime import datetime
from uuid import UUID

class Message:

    role : str = Field(description="Role of the message sender: 'user' or 'bot'")
    text : str = Field(description="Content of message")
    timestamp : Optional[datetime] = Field(None, description="Timestamp of the message")

class ChatRequest(BaseModel):

    chat_id : UUID = Field(description="ID of the new conversation'")
    text : str

class ChatResponse(BaseModel):

    chat_id : UUID = Field(description="ID of the chat")
    messages : List = Field(description="list of messages")

class ChatHistoryItem(BaseModel):

    chat_id : UUID = Field(description="Chat identifier")
    title : Optional[str] = Field(description="first message snippet")
    last_updated : Optional[datetime] = Field(None, description="Last updated timestamp")

class UserRead(schemas.BaseUser[UUID]):
    pass

class UserCreate(schemas.BaseUserCreate):
    pass

class UserUpdate(schemas.BaseUserUpdate):
    pass
