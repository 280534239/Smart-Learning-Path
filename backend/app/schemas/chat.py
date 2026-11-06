"""AI 答疑对话 Schema。"""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class ChatAskRequest(BaseModel):
    """学生提问请求。"""

    subject: str = Field(min_length=1, max_length=80)
    session_id: str = Field(min_length=1, max_length=100)
    message: str = Field(min_length=1, max_length=4000)
    knowledge_context: str | None = Field(
        default=None,
        max_length=50,
    )


class ChatAskData(BaseModel):
    """AI 答疑响应。"""

    reply: str
    subject: str
    session_id: str
    related_knowledge: list[str]


class ChatMessage(BaseModel):
    """对话历史中的一条消息。"""

    role: Literal["user", "assistant"]
    content: str
    timestamp: str | None = None


class ChatHistoryData(BaseModel):
    """完整会话历史。"""

    subject: str
    session_id: str
    messages: list[ChatMessage]
    knowledge_context: str | None
    created_at: datetime


class ChatDeleteData(BaseModel):
    """删除对话结果。"""

    session_id: str
    deleted: bool
