"""自适应学习推荐与学习路径生成引擎。"""

from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.attempt_record import AttemptRecord
from app.models.initial_diagnosis import InitialDiagnosis
from app.models.learning_path import LearningPath
from app.schemas.knowledge import KnowledgeGraphData, KnowledgePointNode
from app.schemas.recommendation import (
    AnalyzeData,
    DailyLearningStat,
    LearningPathStep,
    MasteryPointDetail,
    ProgressData,
    RecentLearningActivity,
    RecommendationItem,
    WeakKnowledgePoint,
)
from app.services.goal_priority_service import normalize_goal_priorities
from app.services.knowledge_service import (
    SubjectNotDeletableError,
    knowledge_service,
)
from app.services.knowledge_tracer import (
    MASTERED_THRESHOLD,
    MasteryBreakdown,
    StudentNotFoundError,
    knowledge_tracer,
)

PREREQUISITE_THRESHOLD = 0.7
ZPD_MIN = 0.3
ZPD_MAX = 0.7
MAX_PATH_STEPS = 8

# 不同难度知识点的建议学习时长，单位为分钟。
ESTIMATED_LEARNING_MINUTES: dict[int, int] = {
    1: 15,
    2: 30,
    3: 45,
    4: 60,
    5: 90,
}


class InitialDiagnosisRequiredError(Exception):
    """进入生成内容前尚未完成初始诊断。"""


@dataclass(frozen=True, slots=True)
class StudentContext:
    """一次分析中复用的用户图谱上下文。"""

    subject: str
    graph: KnowledgeGraphData
    node_by_id: dict[str, KnowledgePointNode]
    mastery_map: dict[str, MasteryBreakdown]
    overall_mastery: float
    overall_level: str
    student_difficulty: float


@dataclass(frozen=True, slots=True)
class ScoredCandidate:
    """内部使用的候选知识点评分。"""

    node: KnowledgePointNode
    mastery: float
    recommendation_score: float
    reason: str


class AdaptiveEngine:
    """基于知识图谱和掌握度生成个性化推荐。"""

    async def recommend_next(
        self,
        student_id: int,
        session: AsyncSession,
        *,
        subject: str,
        top_n: int = 5,
    ) -> list[RecommendationItem]:
        """推荐当前可学习且最适合学生最近发展区的知识点。"""
        context = await self._build_context(
            student_id,
            session,
            subject=subject,
        )
        candidates = self._build_reachable_candidates(context)
        return [
            self._to_recommendation(candidate)
            for candidate in candidates[: max(0, top_n)]
        ]

    async def generate_learning_path(
        self,
        student_id: int,
        session: AsyncSession,
        *,
        subject: str,
        max_steps: int = MAX_PATH_STEPS,
    ) -> list[LearningPathStep]:
        """贪心生成满足前置约束的有序学习路径。"""
        context = await self._build_context(
            student_id,
            session,
            subject=subject,
        )
        return self._generate_learning_path_from_context(
            context,
            max_steps=max_steps,
        )

    def _generate_learning_path_from_context(
        self,
        context: StudentContext,
        *,
        max_steps: int,
    ) -> list[LearningPathStep]:
        """使用已构建的分析上下文生成学习路径。"""
        simulated_mastery = {
            point_id: breakdown.mastery
            for point_id, breakdown in context.mastery_map.items()
        }
        selected_ids: set[str] = set()
        path: list[LearningPathStep] = []

        for step_number in range(1, max(0, max_steps) + 1):
            candidates = self._build_reachable_candidates(
                context,
                mastery_values=simulated_mastery,
                excluded_ids=selected_ids,
            )
            if not candidates:
                break

            selected = candidates[0]
            selected_ids.add(selected.node.id)
            path.append(
                LearningPathStep(
                    step=step_number,
                    knowledge_point_id=selected.node.id,
                    name=selected.node.name,
                    difficulty=selected.node.difficulty,
                    estimated_time=ESTIMATED_LEARNING_MINUTES.get(
                        selected.node.difficulty,
                        ESTIMATED_LEARNING_MINUTES[5],
                    ),
                )
            )

            # 模拟当前步骤完成后解锁后继知识点，使路径保持拓扑正确。
            simulated_mastery[selected.node.id] = MASTERED_THRESHOLD

        return path

    async def analyze(
        self,
        student_id: int,
        session: AsyncSession,
        *,
        subject: str,
    ) -> AnalyzeData:
        """一次构建分析结果、推荐列表和学习路径。"""
        context = await self._build_context(
            student_id,
            session,
            subject=subject,
        )
        await self._ensure_initial_diagnosis_completed(
            student_id,
            context.subject,
            session,
        )
        candidates = self._build_reachable_candidates(context)
        personalized_path = await self._load_personalized_path(
            student_id,
            context,
            session,
        )
        learning_path = (
            personalized_path["steps"]
            if personalized_path is not None
            else self._generate_learning_path_from_context(
                context,
                max_steps=MAX_PATH_STEPS,
            )
        )
        return AnalyzeData(
            subject=context.subject,
            mastery_map={
                point_id: round(breakdown.mastery, 4)
                for point_id, breakdown in context.mastery_map.items()
            },
            overall_level=context.overall_level,
            overall_mastery=round(context.overall_mastery, 4),
            recommendations=[
                self._to_recommendation(candidate)
                for candidate in candidates[:5]
            ],
            learning_path=learning_path,
            learning_goal=(
                personalized_path["learning_goal"]
                if personalized_path is not None
                else None
            ),
            goal_priorities=(
                personalized_path["goal_priorities"]
                if personalized_path is not None
                else []
            ),
            path_summary=(
                personalized_path["path_summary"]
                if personalized_path is not None
                else None
            ),
        )

    @staticmethod
    async def _ensure_initial_diagnosis_completed(
        student_id: int,
        subject: str,
        session: AsyncSession,
    ) -> None:
        """生成内容必须完成初始诊断后才能进入学习分析。"""
        try:
            await knowledge_service.get_generated_subject(subject)
        except SubjectNotDeletableError:
            return

        completed_id = await session.scalar(
            select(InitialDiagnosis.id)
            .where(
                InitialDiagnosis.user_id == student_id,
                InitialDiagnosis.subject == subject,
                InitialDiagnosis.status == "completed",
            )
            .limit(1)
        )
        if completed_id is None:
            raise InitialDiagnosisRequiredError(
                "请先完成该学习内容的初始诊断"
            )

    @staticmethod
    async def _load_personalized_path(
        student_id: int,
        context: StudentContext,
        session: AsyncSession,
    ) -> dict[str, object] | None:
        """读取初始诊断完成后保存的个性化学习路径。"""
        record = await session.scalar(
            select(LearningPath)
            .where(
                LearningPath.user_id == student_id,
                LearningPath.subject == context.subject,
                LearningPath.is_active.is_(True),
            )
            .order_by(LearningPath.generated_at.desc())
            .limit(1)
        )
        if record is None or not isinstance(record.path_data, dict):
            return None

        raw_steps = record.path_data.get("steps")
        if not isinstance(raw_steps, list):
            return None
        valid_ids = set(context.node_by_id)
        try:
            steps = [
                LearningPathStep.model_validate(step)
                for step in raw_steps
                if isinstance(step, dict)
                and step.get("knowledge_point_id") in valid_ids
            ]
        except (TypeError, ValueError):
            return None
        if not steps:
            return None
        raw_priorities = record.path_data.get("goal_priorities")
        learning_goal = str(record.path_data.get("learning_goal") or "")
        goal_priorities = normalize_goal_priorities(
            (
                [str(item) for item in raw_priorities]
                if isinstance(raw_priorities, list)
                else None
            ),
            learning_goal,
        )
        return {
            "steps": steps,
            "learning_goal": learning_goal or None,
            "goal_priorities": goal_priorities,
            "path_summary": record.path_data.get("path_summary"),
        }

    async def get_progress(
        self,
        student_id: int,
        session: AsyncSession,
        *,
        subject: str,
    ) -> ProgressData:
        """返回知识点掌握度详情和整体进度。"""
        context = await self._build_context(
            student_id,
            session,
            subject=subject,
        )
        points = [
            self._to_mastery_detail(node, context.mastery_map[node.id])
            for node in context.graph.nodes
        ]
        attempts = list(
            (
                await session.scalars(
                    select(AttemptRecord)
                    .where(
                        AttemptRecord.user_id == student_id,
                        AttemptRecord.subject == context.subject,
                    )
                    .order_by(AttemptRecord.created_at.desc())
                )
            ).all()
        )
        now = datetime.now(UTC)
        week_start = now - timedelta(days=now.weekday())
        week_start = week_start.replace(
            hour=0,
            minute=0,
            second=0,
            microsecond=0,
        )
        weekly_attempts = [
            attempt
            for attempt in attempts
            if self._to_utc(attempt.created_at) >= week_start
        ]
        weekly_questions = len(weekly_attempts)
        weekly_accuracy = (
            sum(
                1 for attempt in weekly_attempts if attempt.is_correct
            )
            / weekly_questions
            if weekly_questions
            else 0.0
        )
        weak_points = sorted(
            (
                WeakKnowledgePoint(
                    knowledge_point_id=point.knowledge_point_id,
                    name=point.name,
                    category=point.category,
                    mastery=point.mastery,
                )
                for point in points
                if point.attempt_count > 0 and point.mastery < 0.5
            ),
            key=lambda point: point.mastery,
        )[:5]
        return ProgressData(
            user_id=student_id,
            subject=context.subject,
            overall_level=context.overall_level,
            overall_mastery=round(context.overall_mastery, 4),
            total_points=len(points),
            assessed_points=sum(
                1 for point in points if point.attempt_count > 0
            ),
            mastered_points=sum(
                1 for point in points if point.is_mastered
            ),
            points=points,
            study_streak_days=self._study_streak_days(attempts, now),
            total_study_minutes=round(
                sum(attempt.time_spent for attempt in attempts) / 60
            ),
            weekly_questions=weekly_questions,
            weekly_accuracy=round(weekly_accuracy, 4),
            weekly_study_minutes=round(
                sum(attempt.time_spent for attempt in weekly_attempts) / 60
            ),
            recent_activities=[
                RecentLearningActivity(
                    id=attempt.id,
                    activity_type="practice",
                    knowledge_point_id=attempt.knowledge_point_id,
                    knowledge_point_name=(
                        context.node_by_id[
                            attempt.knowledge_point_id
                        ].name
                        if attempt.knowledge_point_id
                        in context.node_by_id
                        else attempt.knowledge_point_id
                    ),
                    is_correct=attempt.is_correct,
                    time_spent=attempt.time_spent,
                    created_at=attempt.created_at,
                )
                for attempt in attempts[:6]
            ],
            weak_points=weak_points,
            daily_activity=self._build_daily_activity(attempts, now),
        )

    async def _build_context(
        self,
        student_id: int,
        session: AsyncSession,
        *,
        subject: str,
    ) -> StudentContext:
        """加载图谱和全部掌握度，并计算学生整体水平。"""
        graph = await knowledge_service.get_graph(subject)
        mastery_map = await knowledge_tracer.calculate_mastery_map(
            student_id,
            session,
            subject=subject,
        )
        node_by_id = {node.id: node for node in graph.nodes}
        assessed = [
            breakdown
            for breakdown in mastery_map.values()
            if breakdown.attempt_count > 0
        ]
        overall_mastery = (
            sum(item.mastery for item in assessed) / len(assessed)
            if assessed
            else 0.0
        )
        student_difficulty = self._calculate_student_difficulty(
            mastery_map,
            node_by_id,
        )
        return StudentContext(
            subject=graph.subject,
            graph=graph,
            node_by_id=node_by_id,
            mastery_map=mastery_map,
            overall_mastery=overall_mastery,
            overall_level=self._level_name(overall_mastery, bool(assessed)),
            student_difficulty=student_difficulty,
        )

    def _build_reachable_candidates(
        self,
        context: StudentContext,
        *,
        mastery_values: dict[str, float] | None = None,
        excluded_ids: set[str] | None = None,
    ) -> list[ScoredCandidate]:
        """筛选前置达标且尚未掌握的知识点并按推荐分排序。"""
        if mastery_values is None:
            mastery_values = {
                point_id: breakdown.mastery
                for point_id, breakdown in context.mastery_map.items()
            }
        if excluded_ids is None:
            excluded_ids = set()
        candidates: list[ScoredCandidate] = []

        for node in context.graph.nodes:
            if node.id in excluded_ids:
                continue

            mastery = mastery_values[node.id]
            if mastery >= MASTERED_THRESHOLD:
                continue

            prerequisites_ready = all(
                mastery_values[prerequisite] >= PREREQUISITE_THRESHOLD
                for prerequisite in node.prerequisites
            )
            if not prerequisites_ready:
                continue

            zone_score = self._zone_score(mastery)
            difficulty_fit = self._difficulty_fit(
                knowledge_difficulty=node.difficulty,
                student_difficulty=context.student_difficulty,
            )
            recommendation_score = (
                0.6 * zone_score + 0.4 * difficulty_fit
            )
            candidates.append(
                ScoredCandidate(
                    node=node,
                    mastery=mastery,
                    recommendation_score=self._clamp(recommendation_score),
                    reason=self._recommendation_reason(mastery),
                )
            )

        return sorted(
            candidates,
            key=lambda item: (
                -item.recommendation_score,
                item.node.difficulty,
                item.node.id,
            ),
        )

    @staticmethod
    def _calculate_student_difficulty(
        mastery_map: dict[str, MasteryBreakdown],
        node_by_id: dict[str, KnowledgePointNode],
    ) -> float:
        """按掌握度加权计算学生当前所处的知识点难度。"""
        weighted_difficulty = 0.0
        total_weight = 0.0
        for point_id, breakdown in mastery_map.items():
            if breakdown.attempt_count == 0 or breakdown.mastery == 0:
                continue
            weighted_difficulty += (
                node_by_id[point_id].difficulty * breakdown.mastery
            )
            total_weight += breakdown.mastery

        if total_weight == 0:
            return 1.0
        return max(1.0, min(5.0, weighted_difficulty / total_weight))

    @staticmethod
    def _zone_score(mastery: float) -> float:
        """最近发展区得分，掌握度接近 0.5 时最高。"""
        return AdaptiveEngine._clamp(1.0 - abs(mastery - 0.5) * 2)

    @staticmethod
    def _difficulty_fit(
        *,
        knowledge_difficulty: int,
        student_difficulty: float,
    ) -> float:
        """知识点难度与学生当前水平越接近，匹配分越高。"""
        return AdaptiveEngine._clamp(
            1.0 - abs(knowledge_difficulty - student_difficulty) / 4.0
        )

    @staticmethod
    def _recommendation_reason(mastery: float) -> str:
        """根据当前掌握度生成可解释的推荐理由。"""
        if ZPD_MIN <= mastery <= ZPD_MAX:
            return "你已掌握前置知识，这个知识点正处于最佳学习区间"
        if mastery < ZPD_MIN:
            return "前置知识已达标，适合从该知识点开始建立当前阶段基础"
        return "你已接近掌握该知识点，建议通过针对性练习完成巩固"

    @staticmethod
    def _level_name(
        overall_mastery: float,
        has_assessment: bool,
    ) -> str:
        """根据已评估知识点的平均掌握度划分整体水平。"""
        if not has_assessment:
            return "入门"
        if overall_mastery < 0.3:
            return "入门"
        if overall_mastery < 0.55:
            return "基础"
        if overall_mastery < 0.75:
            return "进阶"
        if overall_mastery < 0.9:
            return "熟练"
        return "高级"

    @staticmethod
    def _to_recommendation(
        candidate: ScoredCandidate,
    ) -> RecommendationItem:
        """转换内部候选为接口推荐模型。"""
        return RecommendationItem(
            knowledge_point_id=candidate.node.id,
            name=candidate.node.name,
            description=candidate.node.description,
            category=candidate.node.category,
            difficulty=candidate.node.difficulty,
            current_mastery=round(candidate.mastery, 4),
            recommendation_score=round(
                candidate.recommendation_score,
                4,
            ),
            reason=candidate.reason,
        )

    @staticmethod
    def _to_mastery_detail(
        node: KnowledgePointNode,
        breakdown: MasteryBreakdown,
    ) -> MasteryPointDetail:
        """转换内部掌握度数据为看板模型。"""
        return MasteryPointDetail(
            knowledge_point_id=node.id,
            name=node.name,
            category=node.category,
            difficulty=node.difficulty,
            mastery=round(breakdown.mastery, 4),
            correct_rate=round(breakdown.correct_rate, 4),
            efficiency_score=round(breakdown.efficiency_score, 4),
            recency_score=round(breakdown.recency_score, 4),
            attempt_count=breakdown.attempt_count,
            is_mastered=breakdown.is_mastered,
        )

    @staticmethod
    def _clamp(value: float) -> float:
        """将得分限制在 0 到 1。"""
        return max(0.0, min(1.0, value))

    @staticmethod
    def _to_utc(value: datetime) -> datetime:
        """将 SQLite 返回的朴素时间按 UTC 处理。"""
        if value.tzinfo is None:
            return value.replace(tzinfo=UTC)
        return value.astimezone(UTC)

    @classmethod
    def _study_streak_days(
        cls,
        attempts: list[AttemptRecord],
        now: datetime,
    ) -> int:
        """计算截至今天或昨天的连续学习天数。"""
        if not attempts:
            return 0

        learning_days = {
            cls._to_utc(attempt.created_at).date()
            for attempt in attempts
        }
        cursor = now.date()
        if cursor not in learning_days:
            cursor -= timedelta(days=1)
        if cursor not in learning_days:
            return 0

        streak = 0
        while cursor in learning_days:
            streak += 1
            cursor -= timedelta(days=1)
        return streak

    @classmethod
    def _build_daily_activity(
        cls,
        attempts: list[AttemptRecord],
        now: datetime,
    ) -> list[DailyLearningStat]:
        """聚合最近 30 天答题量、正确率和累计掌握趋势。"""
        start_date = now.date() - timedelta(days=29)
        attempts_by_day: dict[date, list[AttemptRecord]] = {}
        for attempt in attempts:
            attempt_date = cls._to_utc(attempt.created_at).date()
            attempts_by_day.setdefault(attempt_date, []).append(attempt)

        cumulative: dict[str, list[int]] = {}
        daily_stats: list[DailyLearningStat] = []
        for offset in range(30):
            current_date = start_date + timedelta(days=offset)
            day_attempts = attempts_by_day.get(current_date, [])
            for attempt in day_attempts:
                counters = cumulative.setdefault(
                    attempt.knowledge_point_id,
                    [0, 0],
                )
                counters[1] += 1
                if attempt.is_correct:
                    counters[0] += 1

            day_questions = len(day_attempts)
            day_correct = sum(
                1 for attempt in day_attempts if attempt.is_correct
            )
            mastery = (
                sum(
                    correct / total
                    for correct, total in cumulative.values()
                    if total
                )
                / len(cumulative)
                if cumulative
                else 0.0
            )
            daily_stats.append(
                DailyLearningStat(
                    date=current_date.isoformat(),
                    questions=day_questions,
                    correct=day_correct,
                    accuracy=(
                        day_correct / day_questions
                        if day_questions
                        else 0.0
                    ),
                    study_minutes=round(
                        sum(
                            attempt.time_spent
                            for attempt in day_attempts
                        )
                        / 60
                    ),
                    mastery=round(cls._clamp(mastery), 4),
                )
            )
        return daily_stats


adaptive_engine = AdaptiveEngine()

__all__ = [
    "AdaptiveEngine",
    "StudentNotFoundError",
    "adaptive_engine",
]
