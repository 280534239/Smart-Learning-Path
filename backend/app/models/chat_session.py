"""对话历史模型。"""

from typing import TYPE_CHECKING, Any

from sqlalchemy import ForeignKey, Index, JSON, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import CreatedAtMixin

if TYPE_CHECKING:
    from app.models.user import User


class ChatSession(CreatedAtMixin, Base):
    """用户与 AI 私教的一次会话历史。"""

    __tablename__ = "chat_sessions"
    __table_args__ = (
        Index(
            "ix_chat_sessions_user_session",
            "user_id",
            "session_id",
        ),
        Index(
            "ix_chat_sessions_user_subject_session",
            "user_id",
            "subject",
            "session_id",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    subject: Mapped[str] = mapped_column(
        String(80),
        nullable=False,
    )
    session_id: Mapped[str] = mapped_column(String(100), nullable=False)
    messages: Mapped[list[dict[str, Any]]] = mapped_column(JSON, nullable=False)
    knowledge_context: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
    )

    user: Mapped["User"] = relationship(back_populates="chat_sessions")
