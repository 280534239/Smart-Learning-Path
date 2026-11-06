"""自适应推荐与学习进度 Schema。"""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class AnalyzeRequest(BaseModel):
    """学习分析请求。"""

    subject: str = Field(min_length=1, max_length=80)


class RecommendationItem(BaseModel):
    """单个推荐知识点。"""

    knowledge_point_id: str
    name: str
    description: str
    category: str
    difficulty: int = Field(ge=1, le=5)
    current_mastery: float = Field(ge=0.0, le=1.0)
    recommendation_score: float = Field(ge=0.0, le=1.0)
    reason: str


class LearningPathStep(BaseModel):
    """学习路径中的一个步骤。"""

    step: int = Field(ge=1)
    knowledge_point_id: str
    name: str
    difficulty: int = Field(ge=1, le=5)
    estimated_time: int = Field(gt=0, description="预计学习时间，单位：分钟")


class AnalyzeData(BaseModel):
    """学习分析与推荐结果。"""

    subject: str
    mastery_map: dict[str, float]
    overall_level: str
    overall_mastery: float = Field(ge=0.0, le=1.0)
    recommendations: list[RecommendationItem]
    learning_path: list[LearningPathStep]
    learning_goal: str | None = None
    goal_priorities: list[str] = Field(default_factory=list)
    path_summary: str | None = None


class MasteryPointDetail(BaseModel):
    """单个知识点的掌握度明细。"""

    knowledge_point_id: str
    name: str
    category: str
    difficulty: int = Field(ge=1, le=5)
    mastery: float = Field(ge=0.0, le=1.0)
    correct_rate: float = Field(ge=0.0, le=1.0)
    efficiency_score: float = Field(ge=0.0, le=1.0)
    recency_score: float = Field(ge=0.0, le=1.0)
    attempt_count: int = Field(ge=0)
    is_mastered: bool


class RecentLearningActivity(BaseModel):
    """最近一次练习活动。"""

    id: int
    activity_type: Literal["practice"]
    knowledge_point_id: str
    knowledge_point_name: str
    is_correct: bool
    time_spent: int = Field(ge=0)
    created_at: datetime


class WeakKnowledgePoint(BaseModel):
    """需要优先巩固的薄弱知识点。"""

    knowledge_point_id: str
    name: str
    category: str
    mastery: float = Field(ge=0.0, le=1.0)


class DailyLearningStat(BaseModel):
    """单个自然日的学习统计。"""

    date: str
    questions: int = Field(ge=0)
    correct: int = Field(ge=0)
    accuracy: float = Field(ge=0.0, le=1.0)
    study_minutes: int = Field(ge=0)
    mastery: float = Field(ge=0.0, le=1.0)


class ProgressData(BaseModel):
    """用户学习进度看板数据。"""

    user_id: int
    subject: str
    overall_level: str
    overall_mastery: float = Field(ge=0.0, le=1.0)
    total_points: int = Field(ge=0)
    assessed_points: int = Field(ge=0)
    mastered_points: int = Field(ge=0)
    points: list[MasteryPointDetail]
    study_streak_days: int = Field(default=0, ge=0)
    total_study_minutes: int = Field(default=0, ge=0)
    weekly_questions: int = Field(default=0, ge=0)
    weekly_accuracy: float = Field(default=0.0, ge=0.0, le=1.0)
    weekly_study_minutes: int = Field(default=0, ge=0)
    recent_activities: list[RecentLearningActivity] = Field(
        default_factory=list
    )
    weak_points: list[WeakKnowledgePoint] = Field(default_factory=list)
    daily_activity: list[DailyLearningStat] = Field(default_factory=list)
