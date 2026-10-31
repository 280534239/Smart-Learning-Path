"""系统健康检查路由。"""

from datetime import UTC, datetime

from fastapi import APIRouter, Response
from pydantic import BaseModel

from app.core.config import get_settings
from app.core.response import ApiResponse

router = APIRouter(tags=["系统"])
settings = get_settings()


class HealthData(BaseModel):
    """健康检查返回数据。"""

    status: str
    service: str
    version: str
    timestamp: datetime


@router.get(
    "/health",
    response_model=ApiResponse[HealthData],
    summary="检查后端服务状态",
)
async def health_check(response: Response) -> ApiResponse[HealthData]:
    """返回后端服务运行状态。"""
    response.headers["Cache-Control"] = "no-store"
    return ApiResponse[HealthData](
        code=0,
        message="服务运行正常",
        data=HealthData(
            status="ok",
            service=settings.app_name,
            version=settings.app_version,
            timestamp=datetime.now(UTC),
        ),
    )
