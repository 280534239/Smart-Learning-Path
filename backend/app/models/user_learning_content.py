"""用户与模型生成学习内容的归属关系。"""

from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import CreatedAtMixin

if TYPE_CHECKING:
    from app.models.user import User


class UserLearningContent(CreatedAtMixin, Base):
    """记录一份模型生成内容所属的用户。"""

    __tablename__ = "user_learning_contents"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    subject: Mapped[str] = mapped_column(
        String(80),
        unique=True,
        index=True,
        nullable=False,
    )

    user: Mapped["User"] = relationship(back_populates="learning_contents")
