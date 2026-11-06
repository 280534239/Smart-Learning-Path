"""初始诊断相关 Schema。"""

from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.practice import PracticeQuestion
from app.schemas.recommendation import AnalyzeData, ProgressData

LearningLevel = Literal["入门", "基础", "进阶", "高级"]


class InitialDiagnosisStatusData(BaseModel):
    """当前用户对一份学习内容的初始诊断状态。"""

    subject: str
    title: str
    required: bool
    completed: bool
    session_id: int | None = None
    learning_goal: str | None = None
    level: LearningLevel | None = None


class StartInitialDiagnosisRequest(BaseModel):
    """创建或恢复初始诊断时可覆盖的学习需求。"""

    goal: str | None = Field(default=None, max_length=500)
    level: LearningLevel | None = None


class StartInitialDiagnosisData(BaseModel):
    """初始诊断题目与用户上下文。"""

    session_id: int
    subject: str
    title: str
    learning_goal: str
    level: LearningLevel
    questions: list[PracticeQuestion]


class InitialDiagnosisAnswer(BaseModel):
    """一道初始诊断题的作答。"""

    question_id: str = Field(min_length=1, max_length=50)
    answer: str = Field(min_length=1, max_length=2000)
    time_spent: int = Field(ge=0)


class CompleteInitialDiagnosisRequest(BaseModel):
    """提交整套初始诊断答案。"""

    answers: list[InitialDiagnosisAnswer] = Field(min_length=1)


class CompleteInitialDiagnosisData(BaseModel):
    """初始诊断结果与据此生成的个性化路径。"""

    session_id: int
    subject: str
    learning_goal: str
    answered_count: int = Field(ge=1)
    correct_count: int = Field(ge=0)
    accuracy: float = Field(ge=0.0, le=1.0)
    path_summary: str
    analysis: AnalyzeData
    progress: ProgressData
