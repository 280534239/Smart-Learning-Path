"""知识图谱查询路由。"""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.llm import LLMServiceError
from app.core.response import ApiResponse
from app.routers.auth import CurrentUser
from app.schemas.knowledge import (
    CategoryGraphData,
    GenerateSubjectRequest,
    KnowledgeGraphData,
    KnowledgePointDetail,
    KnowledgePointResources,
    SubjectDeletionData,
    SubjectListData,
)
from app.services.content_generation_service import (
    ContentGenerationError,
    ContentGenerationUnavailableError,
    content_generation_service,
)
from app.services.knowledge_service import (
    KnowledgePointNotFoundError,
    SubjectNotDeletableError,
    SubjectNotFoundError,
    knowledge_service,
)
from app.services.initial_diagnosis_service import (
    initial_diagnosis_service,
)
from app.services.learning_content_access_service import (
    LearningContentAccessDeniedError,
    learning_content_access_service,
)
from app.services.subject_deletion_service import subject_deletion_service

router = APIRouter()
DatabaseSession = Annotated[AsyncSession, Depends(get_db)]


@router.get(
    "/subjects",
    response_model=ApiResponse[SubjectListData],
    status_code=status.HTTP_200_OK,
    summary="获取可选学习内容",
)
async def list_subjects(
    db: DatabaseSession,
    current_user: CurrentUser,
) -> ApiResponse[SubjectListData]:
    """返回当前用户生成的学习内容。"""
    data = await knowledge_service.list_subjects()
    generated_subjects = {
        item.subject for item in data.subjects if item.generated
    }
    accessible = (
        await learning_content_access_service
        .list_accessible_generated_subjects(
            user_id=current_user.id,
            generated_subjects=generated_subjects,
            session=db,
        )
    )
    data.subjects = [
        item
        for item in data.subjects
        if not item.generated or item.subject in accessible
    ]
    data.default_subject = (
        data.subjects[0].subject if data.subjects else ""
    )
    return ApiResponse[SubjectListData](
        code=status.HTTP_200_OK,
        message="获取学习内容列表成功",
        data=data,
    )


@router.post(
    "/subjects/generate",
    response_model=ApiResponse[KnowledgeGraphData],
    status_code=status.HTTP_200_OK,
    summary="通过模型生成学习内容",
)
async def generate_subject(
    payload: GenerateSubjectRequest,
    db: DatabaseSession,
    current_user: CurrentUser,
) -> ApiResponse[KnowledgeGraphData]:
    """根据用户输入的主题生成并保存一份知识图谱。"""
    try:
        data = await content_generation_service.generate_subject(
            payload,
            owner_user_id=current_user.id,
        )
    except ContentGenerationUnavailableError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc
    except (ContentGenerationError, LLMServiceError) as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc

    await initial_diagnosis_service.prepare_for_new_subject(
        user_id=current_user.id,
        subject=data.subject,
        goal=payload.goal,
        goal_priorities=payload.goal_priorities,
        level=payload.level,
        session=db,
    )

    return ApiResponse[KnowledgeGraphData](
        code=status.HTTP_200_OK,
        message="学习内容生成成功",
        data=data,
    )


@router.delete(
    "/subjects/{subject}",
    response_model=ApiResponse[SubjectDeletionData],
    status_code=status.HTTP_200_OK,
    summary="删除学习内容及其全部关联数据",
)
async def delete_subject(
    subject: str,
    db: DatabaseSession,
    current_user: CurrentUser,
) -> ApiResponse[SubjectDeletionData]:
    """永久删除模型生成的学习内容及对应的全部学习数据。"""
    try:
        await learning_content_access_service.ensure_access(
            user_id=current_user.id,
            subject=subject,
            session=db,
        )
        data = await subject_deletion_service.delete_subject(
            subject=subject,
            session=db,
        )
    except SubjectNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except SubjectNotDeletableError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    except LearningContentAccessDeniedError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(exc),
        ) from exc

    return ApiResponse[SubjectDeletionData](
        code=status.HTTP_200_OK,
        message="学习内容及其关联数据已删除",
        data=data,
    )


@router.get(
    "/graph/{subject}",
    response_model=ApiResponse[KnowledgeGraphData],
    status_code=status.HTTP_200_OK,
    summary="获取完整知识图谱",
)
async def get_graph(
    subject: str,
    db: DatabaseSession,
    current_user: CurrentUser,
) -> ApiResponse[KnowledgeGraphData]:
    """返回指定学科的节点和可视化边数据。"""
    try:
        await learning_content_access_service.ensure_access(
            user_id=current_user.id,
            subject=subject,
            session=db,
        )
        data = await knowledge_service.get_graph(subject)
    except (
        SubjectNotFoundError,
        KnowledgePointNotFoundError,
    ) as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except LearningContentAccessDeniedError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(exc),
        ) from exc

    return ApiResponse[KnowledgeGraphData](
        code=status.HTTP_200_OK,
        message="获取知识图谱成功",
        data=data,
    )


@router.get(
    "/point/{kp_id}",
    response_model=ApiResponse[KnowledgePointDetail],
    status_code=status.HTTP_200_OK,
    summary="获取知识点详情",
)
async def get_knowledge_point(
    kp_id: str,
    db: DatabaseSession,
    current_user: CurrentUser,
) -> ApiResponse[KnowledgePointDetail]:
    """返回知识点详情、前置知识点、后继知识点和学习资源。"""
    try:
        await learning_content_access_service.ensure_point_access(
            user_id=current_user.id,
            knowledge_point_id=kp_id,
            session=db,
        )
        data = await knowledge_service.get_point(kp_id)
    except KnowledgePointNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except LearningContentAccessDeniedError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(exc),
        ) from exc

    return ApiResponse[KnowledgePointDetail](
        code=status.HTTP_200_OK,
        message="获取知识点成功",
        data=data,
    )


@router.post(
    "/point/{kp_id}/resources",
    response_model=ApiResponse[KnowledgePointResources],
    status_code=status.HTTP_200_OK,
    summary="按需生成知识点详细学习资源",
)
async def generate_knowledge_point_resources(
    kp_id: str,
    db: DatabaseSession,
    current_user: CurrentUser,
) -> ApiResponse[KnowledgePointResources]:
    """为指定知识点生成可在当前页面完整阅读的学习资源。"""
    try:
        await learning_content_access_service.ensure_point_access(
            user_id=current_user.id,
            knowledge_point_id=kp_id,
            session=db,
        )
        point = await knowledge_service.get_point(kp_id)
        resources = (
            await content_generation_service.generate_learning_resources(
                point=point,
            )
        )
    except KnowledgePointNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except LearningContentAccessDeniedError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(exc),
        ) from exc
    except (ContentGenerationError, LLMServiceError) as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc

    data = KnowledgePointResources(
        point_id=point.id,
        point_name=point.name,
        resources=resources,
    )
    return ApiResponse[KnowledgePointResources](
        code=status.HTTP_200_OK,
        message="学习资源生成成功",
        data=data,
    )


@router.get(
    "/categories/{subject}",
    response_model=ApiResponse[CategoryGraphData],
    status_code=status.HTTP_200_OK,
    summary="获取知识图谱分类统计",
)
async def get_categories(
    subject: str,
    db: DatabaseSession,
    current_user: CurrentUser,
) -> ApiResponse[CategoryGraphData]:
    """返回学科分类模块及知识点数量。"""
    try:
        await learning_content_access_service.ensure_access(
            user_id=current_user.id,
            subject=subject,
            session=db,
        )
        data = await knowledge_service.get_categories(subject)
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

    return ApiResponse[CategoryGraphData](
        code=status.HTTP_200_OK,
        message="获取分类统计成功",
        data=data,
    )
