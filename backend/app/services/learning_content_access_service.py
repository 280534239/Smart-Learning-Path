"""模型生成学习内容的用户归属与访问控制。"""

from collections.abc import Iterable

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.attempt_record import AttemptRecord
from app.models.chat_session import ChatSession
from app.models.diagnosis_snapshot import DiagnosisSnapshot
from app.models.error_book import ErrorBook
from app.models.initial_diagnosis import InitialDiagnosis
from app.models.learning_path import LearningPath
from app.models.learning_record import LearningRecord
from app.models.user_learning_content import UserLearningContent
from app.services.knowledge_service import (
    SubjectNotDeletableError,
    knowledge_service,
)

SUBJECT_ACTIVITY_MODELS = (
    AttemptRecord,
    ChatSession,
    DiagnosisSnapshot,
    ErrorBook,
    InitialDiagnosis,
    LearningPath,
    LearningRecord,
)


class LearningContentAccessDeniedError(Exception):
    """当前用户无权访问指定学习内容。"""


class LearningContentAccessService:
    """维护学习内容归属并验证用户访问权限。"""

    async def register_subject(
        self,
        *,
        user_id: int,
        subject: str,
        session: AsyncSession,
    ) -> None:
        """登记新生成内容的归属，同一内容不可归属多个用户。"""
        owner = await session.scalar(
            select(UserLearningContent).where(
                UserLearningContent.subject == subject
            )
        )
        if owner is not None:
            if owner.user_id != user_id:
                raise LearningContentAccessDeniedError(
                    "该学习内容属于其他用户"
                )
            return
        session.add(
            UserLearningContent(user_id=user_id, subject=subject)
        )
        await session.flush()

    async def ensure_access(
        self,
        *,
        user_id: int,
        subject: str,
        session: AsyncSession,
    ) -> None:
        """确认用户可访问自己生成的学习内容。"""
        graph = await knowledge_service.get_graph(subject)
        if not await self._is_generated(graph.subject):
            raise LearningContentAccessDeniedError(
                "无权访问非用户生成的学习内容"
            )

        owner = await session.scalar(
            select(UserLearningContent).where(
                UserLearningContent.subject == graph.subject
            )
        )
        if owner is not None:
            if owner.user_id != user_id:
                raise LearningContentAccessDeniedError(
                    "无权访问其他用户的学习内容"
                )
            return

        legacy_subjects = await self._find_legacy_subjects(
            user_id=user_id,
            subjects={graph.subject},
            session=session,
        )
        if graph.subject not in legacy_subjects:
            raise LearningContentAccessDeniedError(
                "无权访问其他用户的学习内容"
            )
        await self.register_subject(
            user_id=user_id,
            subject=graph.subject,
            session=session,
        )
        await session.commit()

    async def ensure_point_access(
        self,
        *,
        user_id: int,
        knowledge_point_id: str,
        session: AsyncSession,
    ) -> str:
        """根据知识点反查内容归属并完成访问校验。"""
        subject = await knowledge_service.get_point_subject(
            knowledge_point_id
        )
        await self.ensure_access(
            user_id=user_id,
            subject=subject,
            session=session,
        )
        return subject

    async def list_accessible_generated_subjects(
        self,
        *,
        user_id: int,
        generated_subjects: Iterable[str],
        session: AsyncSession,
    ) -> set[str]:
        """返回当前用户可看到的模型生成内容。"""
        generated = set(generated_subjects)
        if not generated:
            return set()

        owned_rows = (
            await session.scalars(
                select(UserLearningContent.subject).where(
                    UserLearningContent.user_id == user_id
                )
            )
        ).all()
        owned = set(owned_rows) & generated

        mapped_rows = (
            await session.scalars(
                select(UserLearningContent.subject).where(
                    UserLearningContent.subject.in_(generated)
                )
            )
        ).all()
        unclaimed = generated.difference(mapped_rows)
        legacy = await self._find_legacy_subjects(
            user_id=user_id,
            subjects=unclaimed,
            session=session,
        )
        return owned | legacy

    @staticmethod
    async def _find_legacy_subjects(
        *,
        user_id: int,
        subjects: set[str],
        session: AsyncSession,
    ) -> set[str]:
        """识别旧版本中已通过用户数据关联到当前用户的生成内容。"""
        if not subjects:
            return set()
        matches: set[str] = set()
        for model in SUBJECT_ACTIVITY_MODELS:
            rows = (
                await session.scalars(
                    select(model.subject)
                    .where(
                        model.user_id == user_id,
                        model.subject.in_(subjects),
                    )
                    .distinct()
                )
            ).all()
            matches.update(rows)
            if matches == subjects:
                break
        return matches

    @staticmethod
    async def _is_generated(subject: str) -> bool:
        """判断学习内容是否由模型生成。"""
        graph = await knowledge_service.get_graph(subject)
        try:
            await knowledge_service.get_generated_subject(graph.subject)
        except SubjectNotDeletableError:
            return False
        return True


learning_content_access_service = LearningContentAccessService()
