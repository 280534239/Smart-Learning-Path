"""学习路径模型。"""

from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, JSON, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import utc_now

if TYPE_CHECKING:
    from app.models.user import User


class LearningPath(Base):
    """AI 生成的用户学习路径。"""

    __tablename__ = "learning_paths"
    __table_args__ = (
        Index(
            "ix_learning_paths_user_active",
            "user_id",
            "is_active",
        ),
        Index(
            "ix_learning_paths_user_subject_active",
            "user_id",
            "subject",
            "is_active",
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
    path_data: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    generated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False,
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
    )

    user: Mapped["User"] = relationship(back_populates="learning_paths")
