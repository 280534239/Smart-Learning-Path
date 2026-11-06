"""诊断快照 Schema。"""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class DiagnosisSnapshotData(BaseModel):
    """单次诊断的雷达图数据。"""

    id: int
    subject: str
    source: Literal["initial", "smart"]
    label: str
    category_mastery: dict[str, float]
    overall_mastery: float = Field(ge=0.0, le=1.0)
    answered_count: int = Field(ge=0)
    correct_count: int = Field(ge=0)
    created_at: datetime


class DiagnosisSnapshotListData(BaseModel):
    """按时间排列的全部诊断快照。"""

    subject: str
    categories: list[str]
    snapshots: list[DiagnosisSnapshotData]


class RecordSmartDiagnosisRequest(BaseModel):
    """完成一次智能诊断后记录快照。"""

    subject: str = Field(min_length=1, max_length=80)
    reference_id: str = Field(min_length=1, max_length=100)
