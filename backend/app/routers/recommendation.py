"""自适应推荐路由。"""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.response import ApiResponse
from app.routers.auth import CurrentUser
from app.schemas.recommendation import AnalyzeData, AnalyzeRequest
from app.services.adaptive_engine import (
    InitialDiagnosisRequiredError,
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


@router.post(
    "/analyze",
    response_model=ApiResponse[AnalyzeData],
    status_code=status.HTTP_200_OK,
    summary="分析学习状态并生成推荐",
)
async def analyze_learning(
    payload: AnalyzeRequest,
    db: DatabaseSession,
    current_user: CurrentUser,
) -> ApiResponse[AnalyzeData]:
    """返回掌握度、整体水平、推荐知识点和学习路径。"""
    try:
        await learning_content_access_service.ensure_access(
            user_id=current_user.id,
            subject=payload.subject,
            session=db,
        )
        data = await adaptive_engine.analyze(
            current_user.id,
            db,
            subject=payload.subject,
        )
    except (StudentNotFoundError, SubjectNotFoundError) as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except InitialDiagnosisRequiredError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc
    except LearningContentAccessDeniedError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(exc),
        ) from exc

    return ApiResponse[AnalyzeData](
        code=status.HTTP_200_OK,
        message="学习分析完成",
        data=data,
    )
