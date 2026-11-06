"""答题记录模型。"""

from typing import TYPE_CHECKING

from sqlalchemy import Boolean, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import CreatedAtMixin

if TYPE_CHECKING:
    from app.models.user import User


class AttemptRecord(CreatedAtMixin, Base):
    """用户提交的一次答题记录。"""

    __tablename__ = "attempt_records"
    __table_args__ = (
        Index(
            "ix_attempt_records_user_knowledge",
            "user_id",
            "knowledge_point_id",
        ),
        Index(
            "ix_attempt_records_user_subject",
            "user_id",
            "subject",
        ),
        Index(
            "ix_attempt_records_user_created_at",
            "user_id",
            "created_at",
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
    question_id: Mapped[str] = mapped_column(String(50), nullable=False)
    knowledge_point_id: Mapped[str] = mapped_column(String(50), nullable=False)
    user_answer: Mapped[str] = mapped_column(Text, nullable=False)
    is_correct: Mapped[bool] = mapped_column(Boolean, nullable=False)
    time_spent: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    error_type: Mapped[str | None] = mapped_column(String(50), nullable=True)

    user: Mapped["User"] = relationship(back_populates="attempt_records")
