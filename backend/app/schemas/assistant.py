"""悬浮 AI 小助手请求 Schema。"""

from typing import Literal

from pydantic import BaseModel, Field


class AssistantTurn(BaseModel):
    """悬浮助手上下文中的一轮消息。"""

    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=4000)


class AssistantAskRequest(BaseModel):
    """悬浮助手提问请求。"""

    message: str = Field(min_length=1, max_length=4000)
    subject: str = Field(min_length=1, max_length=80)
    page_title: str | None = Field(default=None, max_length=80)
    knowledge_context: str | None = Field(default=None, max_length=50)
    history: list[AssistantTurn] = Field(
        default_factory=list,
        max_length=10,
    )
