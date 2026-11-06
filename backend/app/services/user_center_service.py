"""用户中心跨学习内容统计聚合。"""

from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.attempt_record import AttemptRecord
from app.models.chat_session import ChatSession
from app.models.diagnosis_snapshot import DiagnosisSnapshot
from app.models.error_book import ErrorBook
from app.models.initial_diagnosis import InitialDiagnosis
from app.models.learning_path import LearningPath
from app.models.learning_record import LearningRecord
from app.schemas.user_center import (
    UserCenterSummaryData,
    UserContentOverview,
    UserDiagnosisOverview,
    UserPathOverview,
)
from app.services.adaptive_engine import adaptive_engine
from app.services.knowledge_service import knowledge_service
from app.services.learning_content_access_service import (
    learning_content_access_service,
)


class UserCenterService:
    """汇总用户跨科目档案、诊断与学习路径。"""

    async def get_summary(
        self,
        *,
        user_id: int,
        session: AsyncSession,
    ) -> UserCenterSummaryData:
        """返回用户中心一期所需的全部统计。"""
        attempts = list(
            (
                await session.scalars(
                    select(AttemptRecord)
                    .where(AttemptRecord.user_id == user_id)
                    .order_by(
                        AttemptRecord.created_at.desc(),
                        AttemptRecord.id.desc(),
                    )
                )
            ).all()
        )
        learning_seconds = int(
            await session.scalar(
                select(
                    func.coalesce(func.sum(LearningRecord.time_spent), 0)
                ).where(LearningRecord.user_id == user_id)
            )
            or 0
        )
        error_count = int(
            await session.scalar(
                select(func.count(ErrorBook.id)).where(
                    ErrorBook.user_id == user_id
                )
            )
            or 0
        )
        mastered_error_count = int(
            await session.scalar(
                select(func.count(ErrorBook.id)).where(
                    ErrorBook.user_id == user_id,
                    ErrorBook.is_mastered.is_(True),
                )
            )
            or 0
        )
        chat_session_count = int(
            await session.scalar(
                select(func.count(ChatSession.id)).where(
                    ChatSession.user_id == user_id
                )
            )
            or 0
        )

        subject_summaries = await knowledge_service.list_subjects()
        generated_subjects = {
            item.subject for item in subject_summaries.subjects
        }
        accessible = (
            await learning_content_access_service
            .list_accessible_generated_subjects(
                user_id=user_id,
                generated_subjects=generated_subjects,
                session=session,
            )
        )
        accessible_summaries = [
            item
            for item in subject_summaries.subjects
            if item.subject in accessible
        ]
        subject_titles = {
            item.subject: item.title for item in accessible_summaries
        }

        diagnoses = list(
            (
                await session.scalars(
                    select(InitialDiagnosis)
                    .where(InitialDiagnosis.user_id == user_id)
                    .order_by(
                        InitialDiagnosis.created_at.desc(),
                        InitialDiagnosis.id.desc(),
                    )
                )
            ).all()
        )
        latest_diagnosis_by_subject: dict[str, InitialDiagnosis] = {}
        for diagnosis in diagnoses:
            latest_diagnosis_by_subject.setdefault(
                diagnosis.subject,
                diagnosis,
            )

        content_overviews: list[UserContentOverview] = []
        for summary in accessible_summaries:
            try:
                progress = await adaptive_engine.get_progress(
                    user_id,
                    session,
                    subject=summary.subject,
                )
            except Exception:
                continue
            diagnosis = latest_diagnosis_by_subject.get(summary.subject)
            content_overviews.append(
                UserContentOverview(
                    subject=summary.subject,
                    title=summary.title,
                    description=summary.description,
                    node_count=summary.node_count,
                    overall_mastery=progress.overall_mastery,
                    assessed_points=progress.assessed_points,
                    learning_goal=(
                        diagnosis.learning_goal if diagnosis else None
                    ),
                    level=diagnosis.level if diagnosis else None,
                    diagnosis_completed=(
                        diagnosis is not None
                        and diagnosis.status == "completed"
                    ),
                )
            )

        snapshots = list(
            (
                await session.scalars(
                    select(DiagnosisSnapshot)
                    .where(DiagnosisSnapshot.user_id == user_id)
                    .order_by(
                        DiagnosisSnapshot.created_at.desc(),
                        DiagnosisSnapshot.id.desc(),
                    )
                    .limit(30)
                )
            ).all()
        )
        paths = list(
            (
                await session.scalars(
                    select(LearningPath)
                    .where(LearningPath.user_id == user_id)
                    .order_by(
                        LearningPath.generated_at.desc(),
                        LearningPath.id.desc(),
                    )
                    .limit(20)
                )
            ).all()
        )

        total_attempt_seconds = sum(
            max(0, attempt.time_spent) for attempt in attempts
        )
        correct_count = sum(1 for attempt in attempts if attempt.is_correct)
        total_questions = len(attempts)
        return UserCenterSummaryData(
            total_study_minutes=round(
                (total_attempt_seconds + learning_seconds) / 60
            ),
            total_questions=total_questions,
            overall_accuracy=(
                correct_count / total_questions
                if total_questions
                else 0.0
            ),
            study_streak_days=self._study_streak_days(attempts),
            error_count=error_count,
            mastered_error_count=mastered_error_count,
            chat_session_count=chat_session_count,
            learning_content_count=len(content_overviews),
            contents=content_overviews,
            diagnoses=[
                UserDiagnosisOverview(
                    id=item.id,
                    subject=item.subject,
                    subject_title=subject_titles.get(
                        item.subject,
                        "已删除的学习内容",
                    ),
                    source=item.source,
                    label=item.label,
                    overall_mastery=item.overall_mastery,
                    answered_count=item.answered_count,
                    correct_count=item.correct_count,
                    created_at=item.created_at,
                )
                for item in snapshots
            ],
            learning_paths=[
                UserPathOverview(
                    id=item.id,
                    subject=item.subject,
                    subject_title=subject_titles.get(
                        item.subject,
                        "已删除的学习内容",
                    ),
                    learning_goal=(
                        item.path_data.get("learning_goal")
                        if isinstance(item.path_data, dict)
                        else None
                    ),
                    path_summary=(
                        item.path_data.get("path_summary")
                        if isinstance(item.path_data, dict)
                        else None
                    ),
                    step_count=(
                        len(item.path_data.get("steps", []))
                        if isinstance(item.path_data, dict)
                        and isinstance(item.path_data.get("steps"), list)
                        else 0
                    ),
                    is_active=item.is_active,
                    generated_at=item.generated_at,
                )
                for item in paths
            ],
        )

    @staticmethod
    def _study_streak_days(attempts: list[AttemptRecord]) -> int:
        """计算跨全部学习内容的连续学习天数。"""
        if not attempts:
            return 0
        learning_days = {
            UserCenterService._to_utc(attempt.created_at).date()
            for attempt in attempts
        }
        cursor = datetime.now(UTC).date()
        if cursor not in learning_days:
            cursor -= timedelta(days=1)
        if cursor not in learning_days:
            return 0
        streak = 0
        while cursor in learning_days:
            streak += 1
            cursor -= timedelta(days=1)
        return streak

    @staticmethod
    def _to_utc(value: datetime) -> datetime:
        """把数据库时间统一为 UTC。"""
        if value.tzinfo is None:
            return value.replace(tzinfo=UTC)
        return value.astimezone(UTC)


user_center_service = UserCenterService()
