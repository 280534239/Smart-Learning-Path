"""练习题、答题和错题本路由。"""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.response import ApiResponse
from app.routers.auth import CurrentUser
from app.schemas.practice import (
    ErrorBookData,
    PracticeQuestionData,
    ReviewErrorData,
    ReviewErrorRequest,
    SubmitAnswerData,
    SubmitAnswerRequest,
)
from app.services.practice_service import (
    PracticeNotFoundError,
    practice_service,
)
from app.services.learning_content_access_service import (
    LearningContentAccessDeniedError,
    learning_content_access_service,
)

router = APIRouter()
DatabaseSession = Annotated[AsyncSession, Depends(get_db)]


@router.get(
    "/questions/{kp_id}",
    response_model=ApiResponse[PracticeQuestionData],
    status_code=status.HTTP_200_OK,
    summary="获取知识点练习题",
)
async def get_practice_questions(
    kp_id: str,
    db: DatabaseSession,
    current_user: CurrentUser,
    difficulty: Annotated[int | None, Query(ge=1, le=5)] = None,
    count: Annotated[int, Query(ge=1, le=20)] = 5,
) -> ApiResponse[PracticeQuestionData]:
    """按知识点、难度和数量随机获取练习题，不返回答案。"""
    try:
        await learning_content_access_service.ensure_point_access(
            user_id=current_user.id,
            knowledge_point_id=kp_id,
            session=db,
        )
        data = await practice_service.get_questions(
            kp_id,
            difficulty=difficulty,
            count=count,
        )
    except PracticeNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except LearningContentAccessDeniedError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(exc),
        ) from exc

    return ApiResponse[PracticeQuestionData](
        code=status.HTTP_200_OK,
        message="获取练习题成功",
        data=data,
    )


@router.post(
    "/submit",
    response_model=ApiResponse[SubmitAnswerData],
    status_code=status.HTTP_200_OK,
    summary="提交并自动批改答案",
)
async def submit_answer(
    payload: SubmitAnswerRequest,
    db: DatabaseSession,
    current_user: CurrentUser,
) -> ApiResponse[SubmitAnswerData]:
    """自动批改答案，记录答题结果并更新知识点掌握度。"""
    try:
        question = await practice_service.get_question(payload.question_id)
        await learning_content_access_service.ensure_point_access(
            user_id=current_user.id,
            knowledge_point_id=question.knowledge_point_id,
            session=db,
        )
        data = await practice_service.submit_answer(
            user_id=current_user.id,
            question_id=payload.question_id,
            answer=payload.answer,
            time_spent=payload.time_spent,
            session=db,
        )
    except PracticeNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except LearningContentAccessDeniedError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(exc),
        ) from exc

    return ApiResponse[SubmitAnswerData](
        code=status.HTTP_200_OK,
        message="答题提交成功",
        data=data,
    )


@router.get(
    "/error-book",
    response_model=ApiResponse[ErrorBookData],
    status_code=status.HTTP_200_OK,
    summary="获取用户错题本",
)
async def get_error_book(
    db: DatabaseSession,
    current_user: CurrentUser,
    subject: Annotated[str, Query(min_length=1, max_length=80)],
    knowledge_point_id: Annotated[str | None, Query()] = None,
) -> ApiResponse[ErrorBookData]:
    """返回当前学习内容的错题，可按知识点 ID 筛选。"""
    try:
        await learning_content_access_service.ensure_access(
            user_id=current_user.id,
            subject=subject,
            session=db,
        )
        data = await practice_service.get_error_book(
            user_id=current_user.id,
            session=db,
            subject=subject,
            knowledge_point_id=knowledge_point_id,
        )
    except PracticeNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except LearningContentAccessDeniedError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(exc),
        ) from exc

    return ApiResponse[ErrorBookData](
        code=status.HTTP_200_OK,
        message="获取错题本成功",
        data=data,
    )


@router.post(
    "/error-book/review",
    response_model=ApiResponse[ReviewErrorData],
    status_code=status.HTTP_200_OK,
    summary="标记错题已复习",
)
async def review_error(
    payload: ReviewErrorRequest,
    db: DatabaseSession,
    current_user: CurrentUser,
) -> ApiResponse[ReviewErrorData]:
    """增加错题复习次数并将其标记为已掌握。"""
    try:
        data = await practice_service.review_error(
            user_id=current_user.id,
            error_book_id=payload.error_book_id,
            session=db,
        )
    except PracticeNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc

    return ApiResponse[ReviewErrorData](
        code=status.HTTP_200_OK,
        message="错题已标记为已复习",
        data=data,
    )
