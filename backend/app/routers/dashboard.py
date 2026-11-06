"""学习进度看板路由。"""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.response import ApiResponse
from app.routers.auth import CurrentUser
from app.schemas.recommendation import ProgressData
from app.services.adaptive_engine import (
    StudentNotFoundError,
    adaptive_engine,
)
from app.services.knowledge_service import SubjectNotFoundError
from app.services.learning_content_access_service import (
    LearningContentAccessDeniedError,
    learning_content_access_service,
)

router = APIRouter()
DatabaseSession = Annotated[AsyncSession, Depends(get_db)]


@router.get(
    "/progress",
    response_model=ApiResponse[ProgressData],
    status_code=status.HTTP_200_OK,
    summary="获取用户学习进度",
)
async def get_learning_progress(
    db: DatabaseSession,
    current_user: CurrentUser,
    subject: Annotated[str, Query(min_length=1, max_length=80)],
) -> ApiResponse[ProgressData]:
    """返回全部知识点的掌握度、正确率与近期表现。"""
    try:
        await learning_content_access_service.ensure_access(
            user_id=current_user.id,
            subject=subject,
            session=db,
        )
        data = await adaptive_engine.get_progress(
            current_user.id,
            db,
            subject=subject,
        )
    except (StudentNotFoundError, SubjectNotFoundError) as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except LearningContentAccessDeniedError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(exc),
        ) from exc

    return ApiResponse[ProgressData](
        code=status.HTTP_200_OK,
        message="获取学习进度成功",
        data=data,
    )
