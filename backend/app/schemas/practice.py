"""练习题、答题与错题本 Schema。"""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, model_validator

QuestionType = Literal["choice", "fill_blank", "short_answer"]


class QuestionRecord(BaseModel):
    """题库中的完整题目，包含标准答案与解析。"""

    id: str
    knowledge_point_id: str
    type: QuestionType
    difficulty: int = Field(ge=1, le=5)
    question: str
    options: list[str] = Field(default_factory=list)
    answer: str
    accepted_answers: list[str] = Field(default_factory=list)
    explanation: str

    @model_validator(mode="after")
    def validate_choice_options(self) -> "QuestionRecord":
        """选择题必须提供选项，答案必须是单个选项字母。"""
        if self.type == "choice":
            if len(self.options) < 2:
                raise ValueError("选择题至少需要两个选项")
            normalized_answer = self.answer.strip().upper()
            if (
                len(normalized_answer) != 1
                or not "A" <= normalized_answer <= "Z"
            ):
                raise ValueError("选择题答案必须是选项字母")
        return self


class QuestionBankDocument(BaseModel):
    """单个题库 JSON 文件。"""

    subject: str
    version: str
    description: str
    question_count: int
    questions: list[QuestionRecord]


class PracticeQuestion(BaseModel):
    """返回给前端的题目，不含答案和解析。"""

    id: str
    knowledge_point_id: str
    type: QuestionType
    difficulty: int = Field(ge=1, le=5)
    question: str
    options: list[str]


class PracticeQuestionData(BaseModel):
    """练习题列表响应数据。"""

    subject: str
    knowledge_point_id: str
    count: int = Field(ge=0)
    questions: list[PracticeQuestion]


class SubmitAnswerRequest(BaseModel):
    """提交答案请求。"""

    question_id: str = Field(min_length=1, max_length=50)
    answer: str = Field(min_length=1, max_length=2000)
    time_spent: int = Field(ge=0)


class SubmitAnswerData(BaseModel):
    """自动批改结果。"""

    subject: str
    is_correct: bool
    explanation: str
    mastery_updated: dict[str, float]


class ErrorBookItem(BaseModel):
    """错题本中的单条记录。"""

    id: int
    subject: str
    question_id: str
    knowledge_point_id: str
    question: str
    question_type: QuestionType
    difficulty: int = Field(ge=1, le=5)
    original_answer: str
    correct_answer: str
    explanation: str
    review_count: int = Field(ge=0)
    is_mastered: bool
    created_at: datetime


class ErrorBookData(BaseModel):
    """用户错题本列表。"""

    user_id: int
    subject: str
    count: int = Field(ge=0)
    items: list[ErrorBookItem]


class ReviewErrorRequest(BaseModel):
    """标记错题已复习请求。"""

    error_book_id: int = Field(gt=0)


class ReviewErrorData(BaseModel):
    """错题复习结果。"""

    error_book_id: int
    review_count: int = Field(ge=0)
    is_mastered: bool
