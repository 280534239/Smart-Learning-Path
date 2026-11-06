"""用户学习内容的初始诊断模型。"""

from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, JSON, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import CreatedAtMixin

if TYPE_CHECKING:
    from app.models.user import User


class InitialDiagnosis(CreatedAtMixin, Base):
    """记录用户进入一份学习内容前必须完成的初始诊断。"""

    __tablename__ = "initial_diagnoses"
    __table_args__ = (
        CheckConstraint(
            "status IN ('pending', 'completed')",
            name="ck_initial_diagnoses_status",
        ),
        Index(
            "ix_initial_diagnoses_user_subject",
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
    subject: Mapped[str] = mapped_column(String(80), nullable=False)
    learning_goal: Mapped[str] = mapped_column(
        String(500),
        default="建立系统、可实践的知识体系",
        server_default="建立系统、可实践的知识体系",
        nullable=False,
    )
    level: Mapped[str] = mapped_column(
        String(20),
        default="基础",
        server_default="基础",
        nullable=False,
    )
    status: Mapped[str] = mapped_column(
        String(20),
        default="pending",
        server_default="pending",
        nullable=False,
    )
    questions: Mapped[list[dict[str, Any]] | None] = mapped_column(
        JSON,
        nullable=True,
    )
    result: Mapped[dict[str, Any] | None] = mapped_column(
        JSON,
        nullable=True,
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    user: Mapped["User"] = relationship(back_populates="initial_diagnoses")
