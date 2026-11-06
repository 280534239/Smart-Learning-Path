"""用户中心跨学习内容统计 Schema。"""

from datetime import datetime

from pydantic import BaseModel, Field


class UserContentOverview(BaseModel):
    """单个学习内容的用户进度摘要。"""

    subject: str
    title: str
    description: str
    node_count: int = Field(ge=0)
    overall_mastery: float = Field(ge=0.0, le=1.0)
    assessed_points: int = Field(ge=0)
    learning_goal: str | None = None
    level: str | None = None
    diagnosis_completed: bool = False


class UserDiagnosisOverview(BaseModel):
    """一次诊断快照的摘要。"""

    id: int
    subject: str
    subject_title: str
    source: str
    label: str
    overall_mastery: float = Field(ge=0.0, le=1.0)
    answered_count: int = Field(ge=0)
    correct_count: int = Field(ge=0)
    created_at: datetime


class UserPathOverview(BaseModel):
    """一份个性化学习路径的摘要。"""

    id: int
    subject: str
    subject_title: str
    learning_goal: str | None = None
    path_summary: str | None = None
    step_count: int = Field(ge=0)
    is_active: bool
    generated_at: datetime


class UserCenterSummaryData(BaseModel):
    """用户中心跨学习内容汇总数据。"""

    total_study_minutes: int = Field(ge=0)
    total_questions: int = Field(ge=0)
    overall_accuracy: float = Field(ge=0.0, le=1.0)
    study_streak_days: int = Field(ge=0)
    error_count: int = Field(ge=0)
    mastered_error_count: int = Field(ge=0)
    chat_session_count: int = Field(ge=0)
    learning_content_count: int = Field(ge=0)
    contents: list[UserContentOverview]
    diagnoses: list[UserDiagnosisOverview]
    learning_paths: list[UserPathOverview]
