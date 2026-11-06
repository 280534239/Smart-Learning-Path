"""用户历次诊断的掌握度快照。"""

from typing import TYPE_CHECKING, Any

from sqlalchemy import (
    CheckConstraint,
    Float,
    ForeignKey,
    Index,
    Integer,
    JSON,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import CreatedAtMixin

if TYPE_CHECKING:
    from app.models.user import User


class DiagnosisSnapshot(CreatedAtMixin, Base):
    """保存一次完整诊断对应的模块掌握度。"""

    __tablename__ = "diagnosis_snapshots"
    __table_args__ = (
        CheckConstraint(
            "source IN ('initial', 'smart')",
            name="ck_diagnosis_snapshots_source",
        ),
        UniqueConstraint(
            "user_id",
            "subject",
            "reference_id",
            name="uq_diagnosis_snapshots_reference",
        ),
        Index(
            "ix_diagnosis_snapshots_user_subject_created",
            "user_id",
            "subject",
            "created_at",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    subject: Mapped[str] = mapped_column(String(80), nullable=False)
    source: Mapped[str] = mapped_column(String(20), nullable=False)
    reference_id: Mapped[str] = mapped_column(String(100), nullable=False)
    label: Mapped[str] = mapped_column(String(80), nullable=False)
    category_mastery: Mapped[dict[str, Any]] = mapped_column(
        JSON,
        nullable=False,
    )
    overall_mastery: Mapped[float] = mapped_column(Float, nullable=False)
    answered_count: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )
    correct_count: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )

    user: Mapped["User"] = relationship(back_populates="diagnosis_snapshots")
