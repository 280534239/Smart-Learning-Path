"""初始诊断路由。"""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.response import ApiResponse
from app.routers.auth import CurrentUser
from app.schemas.diagnosis_snapshot import (
    DiagnosisSnapshotData,
    DiagnosisSnapshotListData,
    RecordSmartDiagnosisRequest,
)
from app.schemas.initial_diagnosis import (
    CompleteInitialDiagnosisData,
    CompleteInitialDiagnosisRequest,
    InitialDiagnosisStatusData,
    StartInitialDiagnosisData,
    StartInitialDiagnosisRequest,
)
from app.services.initial_diagnosis_service import (
    InitialDiagnosisNotFoundError,
    InitialDiagnosisStateError,
    InitialDiagnosisUnavailableError,
    initial_diagnosis_service,
)
from app.services.diagnosis_history_service import diagnosis_history_service
from app.services.knowledge_service import SubjectNotFoundError
from app.services.learning_content_access_service import (
    LearningContentAccessDeniedError,
)

router = APIRouter()
DatabaseSession = Annotated[AsyncSession, Depends(get_db)]


@router.get(
    "/snapshots/{subject}",
    response_model=ApiResponse[DiagnosisSnapshotListData],
    status_code=status.HTTP_200_OK,
    summary="获取历次诊断雷达数据",
)
async def list_diagnosis_snapshots(
    subject: str,
    db: DatabaseSession,
    current_user: CurrentUser,
) -> ApiResponse[DiagnosisSnapshotListData]:
    """返回初始诊断和历次智能诊断的掌握度快照。"""
    try:
        data = await diagnosis_history_service.list_snapshots(
            user_id=current_user.id,
            subject=subject,
            session=db,
        )
    except SubjectNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except LearningContentAccessDeniedError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(exc),
        ) from exc
    return ApiResponse[DiagnosisSnapshotListData](
        code=status.HTTP_200_OK,
        message="获取诊断快照成功",
        data=data,
    )


@router.post(
    "/snapshots/smart",
    response_model=ApiResponse[DiagnosisSnapshotData],
    status_code=status.HTTP_200_OK,
    summary="记录一次智能诊断快照",
)
async def record_smart_diagnosis_snapshot(
    payload: RecordSmartDiagnosisRequest,
    db: DatabaseSession,
    current_user: CurrentUser,
) -> ApiResponse[DiagnosisSnapshotData]:
    """在智能诊断完成后记录当前掌握度。"""
    try:
        data = await diagnosis_history_service.record_smart_diagnosis(
            user_id=current_user.id,
            subject=payload.subject,
            reference_id=payload.reference_id,
            session=db,
        )
    except SubjectNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except LearningContentAccessDeniedError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(exc),
        ) from exc
    return ApiResponse[DiagnosisSnapshotData](
        code=status.HTTP_200_OK,
        message="诊断快照已记录",
        data=data,
    )


@router.get(
    "/initial/{subject}/status",
    response_model=ApiResponse[InitialDiagnosisStatusData],
    status_code=status.HTTP_200_OK,
    summary="获取初始诊断状态",
)
async def get_initial_diagnosis_status(
    subject: str,
    db: DatabaseSession,
    current_user: CurrentUser,
) -> ApiResponse[InitialDiagnosisStatusData]:
    """判断当前用户是否可以进入该学习内容。"""
    try:
        data = await initial_diagnosis_service.get_status(
            user_id=current_user.id,
            subject=subject,
            session=db,
        )
    except SubjectNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except LearningContentAccessDeniedError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(exc),
        ) from exc
    return ApiResponse[InitialDiagnosisStatusData](
        code=status.HTTP_200_OK,
        message="获取初始诊断状态成功",
        data=data,
    )


@router.post(
    "/initial/{subject}/start",
    response_model=ApiResponse[StartInitialDiagnosisData],
    status_code=status.HTTP_200_OK,
    summary="开始初始诊断",
)
async def start_initial_diagnosis(
    subject: str,
    payload: StartInitialDiagnosisRequest,
    db: DatabaseSession,
    current_user: CurrentUser,
) -> ApiResponse[StartInitialDiagnosisData]:
    """随机生成并返回覆盖核心模块的初始诊断题。"""
    try:
        data = await initial_diagnosis_service.start(
            user_id=current_user.id,
            subject=subject,
            goal=payload.goal,
            level=payload.level,
            session=db,
        )
    except SubjectNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except InitialDiagnosisStateError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc
    except InitialDiagnosisUnavailableError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc
    except LearningContentAccessDeniedError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(exc),
        ) from exc
    return ApiResponse[StartInitialDiagnosisData](
        code=status.HTTP_200_OK,
        message="初始诊断题目已准备",
        data=data,
    )


@router.post(
    "/initial/{session_id}/complete",
    response_model=ApiResponse[CompleteInitialDiagnosisData],
    status_code=status.HTTP_200_OK,
    summary="提交初始诊断并生成个性化路径",
)
async def complete_initial_diagnosis(
    session_id: int,
    payload: CompleteInitialDiagnosisRequest,
    db: DatabaseSession,
    current_user: CurrentUser,
) -> ApiResponse[CompleteInitialDiagnosisData]:
    """批改全部答案，保存诊断结果并建立个性化学习路径。"""
    try:
        data = await initial_diagnosis_service.complete(
            user_id=current_user.id,
            session_id=session_id,
            answers=payload.answers,
            session=db,
        )
    except InitialDiagnosisNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except InitialDiagnosisStateError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc
    except LearningContentAccessDeniedError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(exc),
        ) from exc
    return ApiResponse[CompleteInitialDiagnosisData](
        code=status.HTTP_200_OK,
        message="初始诊断完成，个性化学习路径已生成",
        data=data,
    )
