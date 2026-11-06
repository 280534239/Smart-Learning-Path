"""用户中心路由。"""

from typing import Annotated

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.response import ApiResponse
from app.routers.auth import CurrentUser
from app.schemas.user_center import UserCenterSummaryData
from app.services.user_center_service import user_center_service

router = APIRouter()
DatabaseSession = Annotated[AsyncSession, Depends(get_db)]


@router.get(
    "/summary",
    response_model=ApiResponse[UserCenterSummaryData],
    status_code=status.HTTP_200_OK,
    summary="获取用户中心跨学习内容统计",
)
async def get_user_center_summary(
    db: DatabaseSession,
    current_user: CurrentUser,
) -> ApiResponse[UserCenterSummaryData]:
    """返回学习档案、诊断记录和路径摘要。"""
    data = await user_center_service.get_summary(
        user_id=current_user.id,
        session=db,
    )
    return ApiResponse[UserCenterSummaryData](
        code=status.HTTP_200_OK,
        message="获取用户中心数据成功",
        data=data,
    )
