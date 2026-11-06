"""学习内容及其全部关联数据的级联删除服务。"""

import asyncio
import logging
from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4

from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.attempt_record import AttemptRecord
from app.models.chat_session import ChatSession
from app.models.diagnosis_snapshot import DiagnosisSnapshot
from app.models.error_book import ErrorBook
from app.models.initial_diagnosis import InitialDiagnosis
from app.models.learning_path import LearningPath
from app.models.learning_record import LearningRecord
from app.models.user_learning_content import UserLearningContent
from app.schemas.knowledge import SubjectDeletionData
from app.services.knowledge_service import (
    GENERATED_GRAPH_DIR,
    knowledge_service,
)
from app.services.practice_service import (
    GENERATED_QUESTION_DIR,
    practice_service,
)
from app.services.rag_service import rag_service

logger = logging.getLogger(__name__)

SUBJECT_DATA_MODELS = (
    AttemptRecord,
    ErrorBook,
    InitialDiagnosis,
    LearningPath,
    LearningRecord,
    ChatSession,
    DiagnosisSnapshot,
    UserLearningContent,
)


@dataclass(frozen=True, slots=True)
class StagedFile:
    """等待数据库事务完成后删除的生成内容文件。"""

    source: Path
    staged: Path


class SubjectDeletionService:
    """删除学习内容、用户学习数据和检索资源。"""

    async def delete_subject(
        self,
        *,
        subject: str,
        session: AsyncSession,
    ) -> SubjectDeletionData:
        """级联删除学习内容并返回各数据表的清理数量。"""
        graph = await knowledge_service.get_generated_subject(subject)
        staged_files = await asyncio.to_thread(
            self._stage_subject_files,
            graph.subject,
        )
        deleted_records: dict[str, int] = {}

        try:
            for model in SUBJECT_DATA_MODELS:
                result = await session.execute(
                    delete(model).where(model.subject == graph.subject)
                )
                deleted_records[model.__tablename__] = max(
                    0,
                    int(result.rowcount or 0),
                )
            await session.commit()
        except Exception:
            await session.rollback()
            await asyncio.to_thread(self._restore_files, staged_files)
            raise

        await asyncio.to_thread(self._remove_staged_files, staged_files)
        await self._refresh_caches(graph.subject)

        return SubjectDeletionData(
            subject=graph.subject,
            title=graph.title,
            deleted_records=deleted_records,
            total_deleted_records=sum(deleted_records.values()),
        )

    @staticmethod
    def _subject_file_paths(subject: str) -> list[Path]:
        """返回模型生成的学习内容和题库文件路径。"""
        graph_files = [
            GENERATED_GRAPH_DIR / f"{subject}.json",
            GENERATED_GRAPH_DIR / f"{subject}.json.tmp",
        ]
        question_files = [
            GENERATED_QUESTION_DIR / f"{subject}.json",
            GENERATED_QUESTION_DIR / f"{subject}.json.tmp",
            GENERATED_QUESTION_DIR / f"{subject}_ai.json",
            GENERATED_QUESTION_DIR / f"{subject}_ai.json.tmp",
        ]
        return [*graph_files, *question_files]

    @classmethod
    def _stage_subject_files(cls, subject: str) -> list[StagedFile]:
        """先把文件移出加载目录，数据库失败时可以完整恢复。"""
        staged_files: list[StagedFile] = []
        try:
            for source in cls._subject_file_paths(subject):
                if not source.is_file():
                    continue
                staged = source.with_name(
                    f".{source.name}.{uuid4().hex}.deleting"
                )
                source.replace(staged)
                staged_files.append(
                    StagedFile(source=source, staged=staged)
                )
        except Exception:
            cls._restore_files(staged_files)
            raise
        return staged_files

    @staticmethod
    def _restore_files(staged_files: list[StagedFile]) -> None:
        """数据库删除失败时恢复暂存的生成内容文件。"""
        for item in staged_files:
            if item.staged.exists():
                item.staged.replace(item.source)

    @staticmethod
    def _remove_staged_files(staged_files: list[StagedFile]) -> None:
        """数据库提交后彻底移除暂存文件。"""
        for item in staged_files:
            try:
                item.staged.unlink(missing_ok=True)
            except OSError:
                logger.exception("无法删除学习内容文件: %s", item.staged)

    @staticmethod
    async def _refresh_caches(subject: str) -> None:
        """刷新知识图谱、题库与向量检索的内存状态。"""
        try:
            await knowledge_service.load_all(force=True)
            await practice_service.load_all(force=True)
        except Exception:
            logger.exception("删除学习内容后刷新内容缓存失败")

        try:
            await rag_service.remove_subject(subject)
        except Exception:
            logger.exception("删除学习内容后刷新向量索引失败")


subject_deletion_service = SubjectDeletionService()
