"""用户模型。"""

from typing import TYPE_CHECKING

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import CreatedAtMixin

if TYPE_CHECKING:
    from app.models.attempt_record import AttemptRecord
    from app.models.chat_session import ChatSession
    from app.models.diagnosis_snapshot import DiagnosisSnapshot
    from app.models.error_book import ErrorBook
    from app.models.initial_diagnosis import InitialDiagnosis
    from app.models.learning_path import LearningPath
    from app.models.learning_record import LearningRecord
    from app.models.user_learning_content import UserLearningContent


class User(CreatedAtMixin, Base):
    """平台用户。"""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(
        String(50),
        unique=True,
        index=True,
        nullable=False,
    )
    email: Mapped[str] = mapped_column(
        String(100),
        unique=True,
        index=True,
        nullable=False,
    )
    nickname: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
    )
    bio: Mapped[str | None] = mapped_column(
        String(280),
        nullable=True,
    )
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    avatar_url: Mapped[str | None] = mapped_column(String(255), nullable=True)

    learning_records: Mapped[list["LearningRecord"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    attempt_records: Mapped[list["AttemptRecord"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    error_book_entries: Mapped[list["ErrorBook"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    initial_diagnoses: Mapped[list["InitialDiagnosis"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    learning_contents: Mapped[list["UserLearningContent"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    learning_paths: Mapped[list["LearningPath"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    chat_sessions: Mapped[list["ChatSession"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    diagnosis_snapshots: Mapped[list["DiagnosisSnapshot"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
