"""知识点掌握度追踪与计算。"""

import math
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.attempt_record import AttemptRecord
from app.models.user import User
from app.services.knowledge_service import knowledge_service

CORRECT_RATE_WEIGHT = 0.5
EFFICIENCY_WEIGHT = 0.2
RECENCY_WEIGHT = 0.3
RECENCY_HALF_LIFE_DAYS = 7.0
MASTERED_THRESHOLD = 0.8

# 标准作答时间按知识点难度设置，单位为秒。
STANDARD_ANSWER_SECONDS: dict[int, int] = {
    1: 30,
    2: 45,
    3: 60,
    4: 90,
    5: 120,
}


class StudentNotFoundError(Exception):
    """学习的用户不存在。"""


@dataclass(frozen=True, slots=True)
class MasteryBreakdown:
    """掌握度总分及其三个可解释维度。"""

    knowledge_point_id: str
    mastery: float
    correct_rate: float
    efficiency_score: float
    recency_score: float
    attempt_count: int
    standard_time_seconds: int

    @property
    def is_mastered(self) -> bool:
        """掌握度达到 0.8 时视为已掌握。"""
        return self.mastery >= MASTERED_THRESHOLD


class KnowledgeTracer:
    """根据答题记录追踪学生对知识点的掌握度。"""

    async def calculate_mastery(
        self,
        student_id: int,
        knowledge_point_id: str,
        session: AsyncSession,
    ) -> MasteryBreakdown:
        """计算指定用户对单个知识点的掌握度。"""
        await self._ensure_student_exists(student_id, session)
        point = await knowledge_service.get_point(knowledge_point_id)
        subject = await knowledge_service.get_point_subject(
            knowledge_point_id
        )
        attempts = await self._load_attempts(
            student_id,
            session,
            subject=subject,
            knowledge_point_id=knowledge_point_id,
        )
        return self._score_attempts(
            knowledge_point_id=knowledge_point_id,
            difficulty=point.difficulty,
            attempts=attempts,
        )

    async def calculate_mastery_map(
        self,
        student_id: int,
        session: AsyncSession,
        *,
        subject: str,
    ) -> dict[str, MasteryBreakdown]:
        """一次查询用户答题记录并计算学科全部知识点掌握度。"""
        await self._ensure_student_exists(student_id, session)
        graph = await knowledge_service.get_graph(subject)
        attempts = await self._load_attempts(
            student_id,
            session,
            subject=subject,
        )

        attempts_by_point: dict[str, list[AttemptRecord]] = {
            node.id: [] for node in graph.nodes
        }
        for attempt in attempts:
            if attempt.knowledge_point_id in attempts_by_point:
                attempts_by_point[attempt.knowledge_point_id].append(attempt)

        return {
            node.id: self._score_attempts(
                knowledge_point_id=node.id,
                difficulty=node.difficulty,
                attempts=attempts_by_point[node.id],
            )
            for node in graph.nodes
        }

    @staticmethod
    async def _ensure_student_exists(
        student_id: int,
        session: AsyncSession,
    ) -> None:
        """确认用户存在，避免对不存在的学生生成虚假推荐。"""
        if await session.get(User, student_id) is None:
            raise StudentNotFoundError(f"用户不存在: {student_id}")

    @staticmethod
    async def _load_attempts(
        student_id: int,
        session: AsyncSession,
        *,
        subject: str | None = None,
        knowledge_point_id: str | None = None,
    ) -> Sequence[AttemptRecord]:
        """按作答时间从旧到新加载用户答题记录。"""
        statement = select(AttemptRecord).where(
            AttemptRecord.user_id == student_id
        )
        if knowledge_point_id is not None:
            statement = statement.where(
                AttemptRecord.knowledge_point_id == knowledge_point_id
            )
        if subject is not None:
            statement = statement.where(
                AttemptRecord.subject == subject
            )
        statement = statement.order_by(
            AttemptRecord.created_at.asc(),
            AttemptRecord.id.asc(),
        )
        result = await session.scalars(statement)
        return result.all()

    def _score_attempts(
        self,
        *,
        knowledge_point_id: str,
        difficulty: int,
        attempts: Sequence[AttemptRecord],
    ) -> MasteryBreakdown:
        """按正确率、效率和近期表现计算掌握度。"""
        standard_time = STANDARD_ANSWER_SECONDS.get(
            difficulty,
            STANDARD_ANSWER_SECONDS[5],
        )
        if not attempts:
            return MasteryBreakdown(
                knowledge_point_id=knowledge_point_id,
                mastery=0.0,
                correct_rate=0.0,
                efficiency_score=0.0,
                recency_score=0.0,
                attempt_count=0,
                standard_time_seconds=standard_time,
            )

        correct_rate = sum(
            1.0 for attempt in attempts if attempt.is_correct
        ) / len(attempts)

        efficiency_score = sum(
            self._calculate_efficiency(
                time_spent=attempt.time_spent,
                standard_time=standard_time,
            )
            for attempt in attempts
        ) / len(attempts)

        recency_score = self._calculate_recency_score(attempts)
        mastery = self._clamp(
            CORRECT_RATE_WEIGHT * correct_rate
            + EFFICIENCY_WEIGHT * efficiency_score
            + RECENCY_WEIGHT * recency_score
        )

        return MasteryBreakdown(
            knowledge_point_id=knowledge_point_id,
            mastery=mastery,
            correct_rate=correct_rate,
            efficiency_score=efficiency_score,
            recency_score=recency_score,
            attempt_count=len(attempts),
            standard_time_seconds=standard_time,
        )

    @staticmethod
    def _calculate_efficiency(
        *,
        time_spent: int,
        standard_time: int,
    ) -> float:
        """计算标准时间与实际用时的比值，结果限制在 0 到 1。"""
        actual_time = max(time_spent, 1)
        return KnowledgeTracer._clamp(standard_time / actual_time)

    @staticmethod
    def _calculate_recency_score(
        attempts: Sequence[AttemptRecord],
    ) -> float:
        """以 7 天半衰期对越近的正确性赋予越高的指数权重。"""
        now = datetime.now(UTC)
        decay_rate = math.log(2) / RECENCY_HALF_LIFE_DAYS
        weighted_correctness = 0.0
        total_weight = 0.0

        for attempt in attempts:
            created_at = attempt.created_at
            if created_at.tzinfo is None:
                created_at = created_at.replace(tzinfo=UTC)
            else:
                created_at = created_at.astimezone(UTC)

            age_days = max(
                (now - created_at).total_seconds() / 86400,
                0.0,
            )
            weight = math.exp(-decay_rate * age_days)
            weighted_correctness += weight * float(attempt.is_correct)
            total_weight += weight

        if total_weight == 0:
            return 0.0
        return KnowledgeTracer._clamp(weighted_correctness / total_weight)

    @staticmethod
    def _clamp(value: float) -> float:
        """将浮点结果限制在 0 到 1。"""
        return max(0.0, min(1.0, value))


knowledge_tracer = KnowledgeTracer()
