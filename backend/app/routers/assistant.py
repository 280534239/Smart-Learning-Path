"""悬浮 AI 小助手路由。"""

import json
from collections.abc import AsyncIterator

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.routers.auth import CurrentUser
from app.schemas.assistant import AssistantAskRequest
from app.services.assistant_service import assistant_service
from app.services.knowledge_service import SubjectNotFoundError
from app.services.learning_content_access_service import (
    LearningContentAccessDeniedError,
    learning_content_access_service,
)

router = APIRouter()


@router.post(
    "/chat/stream",
    status_code=status.HTTP_200_OK,
    summary="向悬浮 AI 小助手流式提问",
)
async def stream_assistant_reply(
    payload: AssistantAskRequest,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
) -> StreamingResponse:
    """使用独立模型流式返回即时回答。"""
    try:
        await learning_content_access_service.ensure_access(
            user_id=current_user.id,
            subject=payload.subject,
            session=db,
        )
        preparation = await assistant_service.prepare(payload)
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

    async def event_stream() -> AsyncIterator[str]:
        yield ": connected\n\n"
        async for event in assistant_service.stream_ask(
            payload,
            preparation,
        ):
            data = json.dumps(event, ensure_ascii=False)
            yield f"data: {data}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
