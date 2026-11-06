"""AI 答疑与对话历史路由。"""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.response import ApiResponse
from app.routers.auth import CurrentUser
from app.schemas.chat import (
    ChatAskData,
    ChatAskRequest,
    ChatDeleteData,
    ChatHistoryData,
)
from app.services.chat_service import (
    ChatNotFoundError,
    chat_service,
)
from app.services.knowledge_service import SubjectNotFoundError
from app.services.learning_content_access_service import (
    LearningContentAccessDeniedError,
    learning_content_access_service,
)

router = APIRouter()
DatabaseSession = Annotated[AsyncSession, Depends(get_db)]


@router.post(
    "/ask",
    response_model=ApiResponse[ChatAskData],
    status_code=status.HTTP_200_OK,
    summary="向智学小助手提问",
)
async def ask_question(
    payload: ChatAskRequest,
    db: DatabaseSession,
    current_user: CurrentUser,
) -> ApiResponse[ChatAskData]:
    """执行 RAG 检索并返回直接回答。"""
    try:
        await learning_content_access_service.ensure_access(
            user_id=current_user.id,
            subject=payload.subject,
            session=db,
        )
        data = await chat_service.ask(current_user.id, payload, db)
    except ChatNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
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

    return ApiResponse[ChatAskData](
        code=status.HTTP_200_OK,
        message="回答生成成功",
        data=data,
    )


@router.get(
    "/history/{session_id}",
    response_model=ApiResponse[ChatHistoryData | None],
    status_code=status.HTTP_200_OK,
    summary="获取对话历史",
)
async def get_chat_history(
    session_id: str,
    db: DatabaseSession,
    current_user: CurrentUser,
    allow_missing: bool = False,
) -> ApiResponse[ChatHistoryData | None]:
    """返回指定会话的全部消息。"""
    try:
        data = await chat_service.get_history(
            current_user.id,
            session_id,
            db,
        )
    except ChatNotFoundError as exc:
        if allow_missing:
            return ApiResponse[ChatHistoryData | None](
                code=status.HTTP_200_OK,
                message=str(exc),
                data=None,
            )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc

    return ApiResponse[ChatHistoryData](
        code=status.HTTP_200_OK,
        message="获取对话历史成功",
        data=data,
    )


@router.delete(
    "/history/{session_id}",
    response_model=ApiResponse[ChatDeleteData],
    status_code=status.HTTP_200_OK,
    summary="删除对话历史",
)
async def delete_chat_history(
    session_id: str,
    db: DatabaseSession,
    current_user: CurrentUser,
) -> ApiResponse[ChatDeleteData]:
    """删除当前登录用户的一条对话记录。"""
    data = await chat_service.delete_history(
        user_id=current_user.id,
        session_id=session_id,
        session=db,
    )
    return ApiResponse[ChatDeleteData](
        code=status.HTTP_200_OK,
        message="对话已删除" if data.deleted else "对话不存在",
        data=data,
    )
