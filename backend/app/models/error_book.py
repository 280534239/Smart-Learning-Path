"""错题本模型。"""

from typing import TYPE_CHECKING

from sqlalchemy import Boolean, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import CreatedAtMixin

if TYPE_CHECKING:
    from app.models.user import User


class ErrorBook(CreatedAtMixin, Base):
    """用户保存的错题及掌握状态。"""

    __tablename__ = "error_book"
    __table_args__ = (
        Index(
            "ix_error_book_user_knowledge",
            "user_id",
            "knowledge_point_id",
        ),
        Index(
            "ix_error_book_user_mastered",
            "user_id",
            "is_mastered",
        ),
        Index(
            "ix_error_book_user_subject",
            "user_id",
            "subject",
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
    original_answer: Mapped[str] = mapped_column(Text, nullable=False)
    correct_answer: Mapped[str] = mapped_column(Text, nullable=False)
    review_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    is_mastered: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )

    user: Mapped["User"] = relationship(back_populates="error_book_entries")
