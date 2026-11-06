"""模型通用字段。"""

from datetime import UTC, datetime

from sqlalchemy import DateTime
from sqlalchemy.orm import Mapped, mapped_column


def utc_now() -> datetime:
    """返回带 UTC 时区的当前时间。"""
    return datetime.now(UTC)


class CreatedAtMixin:
    """为模型提供统一创建时间字段。"""

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False,
    )
