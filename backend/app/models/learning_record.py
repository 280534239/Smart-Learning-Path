"""学习记录模型。"""

from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, Float, ForeignKey, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import CreatedAtMixin

if TYPE_CHECKING:
    from app.models.user import User


class LearningRecord(CreatedAtMixin, Base):
    """用户对知识点的一次学习行为记录。"""

    __tablename__ = "learning_records"
    __table_args__ = (
        CheckConstraint(
            "action_type IN ('learn', 'practice', 'diagnosis')",
            name="ck_learning_records_action_type",
        ),
        Index(
            "ix_learning_records_user_created_at",
            "user_id",
            "created_at",
        ),
        Index(
            "ix_learning_records_user_knowledge",
            "user_id",
            "knowledge_point_id",
        ),
        Index(
            "ix_learning_records_user_subject",
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
    knowledge_point_id: Mapped[str] = mapped_column(String(50), nullable=False)
    action_type: Mapped[str] = mapped_column(String(20), nullable=False)
    time_spent: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    mastery_before: Mapped[float] = mapped_column(Float, nullable=False)
    mastery_after: Mapped[float] = mapped_column(Float, nullable=False)

    user: Mapped["User"] = relationship(back_populates="learning_records")
