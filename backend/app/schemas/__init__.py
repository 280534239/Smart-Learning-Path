"""Pydantic 请求与响应模型。"""

from app.schemas.auth import (
    LoginData,
    LoginRequest,
    RegisterData,
    RegisterRequest,
    UserBrief,
    UserProfile,
)
from app.schemas.chat import ChatAskData, ChatAskRequest, ChatHistoryData
from app.schemas.knowledge import (
    CategoryGraphData,
    KnowledgeGraphData,
    KnowledgePointDetail,
)
from app.schemas.recommendation import (
    AnalyzeData,
    AnalyzeRequest,
    LearningPathStep,
    ProgressData,
    RecommendationItem,
)
from app.schemas.practice import (
    ErrorBookData,
    PracticeQuestionData,
    SubmitAnswerData,
)

__all__ = [
    "AnalyzeData",
    "AnalyzeRequest",
    "CategoryGraphData",
    "ChatAskData",
    "ChatAskRequest",
    "ChatHistoryData",
    "ErrorBookData",
    "KnowledgeGraphData",
    "KnowledgePointDetail",
    "LearningPathStep",
    "LoginData",
    "LoginRequest",
    "RegisterData",
    "RegisterRequest",
    "ProgressData",
    "PracticeQuestionData",
    "RecommendationItem",
    "SubmitAnswerData",
    "UserBrief",
    "UserProfile",
]
