"""FastAPI 应用入口与全局中间件。"""

import logging
import time
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import RequestResponseEndpoint

from app.core.config import get_settings
from app.core.database import engine, init_db
from app.core.exceptions import register_exception_handlers
from app.core.llm import assistant_llm_service, llm_service
from app.core.response import ApiResponse
from app.routers.assistant import router as assistant_router
from app.routers.auth import router as auth_router
from app.routers.chat import router as chat_router
from app.routers.dashboard import router as dashboard_router
from app.routers.health import router as health_router
from app.routers.knowledge import router as knowledge_router
from app.routers.practice import router as practice_router
from app.routers.recommendation import router as recommend_router
from app.services.knowledge_service import knowledge_service
from app.services.practice_service import practice_service
from app.services.rag_service import rag_service

settings = get_settings()
logger = logging.getLogger("app.request")
logger.setLevel(logging.INFO)
logger.propagate = False
if not logger.handlers:
    request_log_handler = logging.StreamHandler()
    request_log_handler.setFormatter(
        logging.Formatter(
            "%(asctime)s | %(levelname)s | %(message)s"
        )
    )
    logger.addHandler(request_log_handler)


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    """按依赖顺序初始化资源，并在关闭时统一清理。"""
    await init_db()
    await knowledge_service.load_all()
    await practice_service.load_all()
    await rag_service.initialize()
    logger.info("应用启动完成")
    try:
        yield
    finally:
        await assistant_llm_service.close()
        await llm_service.close()
        await rag_service.close()
        await engine.dispose()
        logger.info("应用资源已清理")


app = FastAPI(
    title="智学路径 API",
    version=settings.app_version,
    description="基于大模型与知识图谱的AI自适应学习平台",
    debug=settings.debug,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def log_requests(
    request: Request,
    call_next: RequestResponseEndpoint,
) -> Response:
    """记录请求方法、路径、状态码和耗时。"""
    started_at = time.perf_counter()
    try:
        response = await call_next(request)
    except Exception:
        elapsed_ms = (time.perf_counter() - started_at) * 1000
        logger.exception(
            "%s %s failed elapsed=%.2fms",
            request.method,
            request.url.path,
            elapsed_ms,
        )
        raise

    elapsed_ms = (time.perf_counter() - started_at) * 1000
    logger.info(
        "%s %s status=%d elapsed=%.2fms",
        request.method,
        request.url.path,
        response.status_code,
        elapsed_ms,
    )
    return response


register_exception_handlers(app)

app.include_router(health_router, prefix="/api", tags=["系统"])
app.include_router(auth_router, prefix="/api/auth", tags=["认证"])
app.include_router(knowledge_router, prefix="/api/knowledge", tags=["知识图谱"])
app.include_router(recommend_router, prefix="/api/recommend", tags=["推荐"])
app.include_router(practice_router, prefix="/api/practice", tags=["练习"])
app.include_router(chat_router, prefix="/api/chat", tags=["AI答疑"])
app.include_router(
    assistant_router,
    prefix="/api/assistant",
    tags=["悬浮 AI 小助手"],
)
app.include_router(dashboard_router, prefix="/api/dashboard", tags=["数据看板"])


@app.get("/", include_in_schema=False)
async def root() -> ApiResponse[dict[str, str]]:
    """返回服务入口信息。"""
    return ApiResponse[dict[str, str]](
        data={
            "service": settings.app_name,
            "version": settings.app_version,
            "docs": "/docs",
            "health": "/api/health",
        },
    )
