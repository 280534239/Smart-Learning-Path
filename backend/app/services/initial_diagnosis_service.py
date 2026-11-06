"""初始诊断会话与个性化学习路径生成服务。"""

import asyncio
import random
import re
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.attempt_record import AttemptRecord
from app.models.diagnosis_snapshot import DiagnosisSnapshot
from app.models.error_book import ErrorBook
from app.models.initial_diagnosis import InitialDiagnosis
from app.models.learning_path import LearningPath
from app.models.learning_record import LearningRecord
from app.models.user import User
from app.schemas.initial_diagnosis import (
    CompleteInitialDiagnosisData,
    InitialDiagnosisAnswer,
    InitialDiagnosisStatusData,
    StartInitialDiagnosisData,
)
from app.schemas.knowledge import KnowledgeGraphData, KnowledgePointNode
from app.schemas.recommendation import LearningPathStep
from app.services.adaptive_engine import (
    ESTIMATED_LEARNING_MINUTES,
    adaptive_engine,
)
from app.services.knowledge_service import (
    SubjectNotDeletableError,
    knowledge_service,
)
from app.services.diagnosis_history_service import (
    diagnosis_history_service,
)
from app.services.goal_priority_service import (
    DEFAULT_GOAL,
    format_goal_priority_text,
    format_goal_text,
    goal_affinity,
    normalize_goal_priorities,
)
from app.services.learning_content_access_service import (
    learning_content_access_service,
)
from app.services.knowledge_tracer import MASTERED_THRESHOLD
from app.services.practice_service import (
    PracticeNotFoundError,
    practice_service,
)

MAX_PERSONALIZED_PATH_STEPS = 8
MIN_DIAGNOSIS_QUESTIONS = 4
QUESTIONS_PER_POINT = 2
DIAGNOSIS_POINT_COUNT = 4


class InitialDiagnosisError(Exception):
    """初始诊断业务异常基类。"""


class InitialDiagnosisNotFoundError(InitialDiagnosisError):
    """初始诊断会话不存在。"""


class InitialDiagnosisStateError(InitialDiagnosisError):
    """初始诊断会话状态或答案不合法。"""


class InitialDiagnosisUnavailableError(InitialDiagnosisError):
    """暂时无法生成足够的初始诊断题目。"""


class InitialDiagnosisService:
    """管理必须完成的初始诊断及个性化路径生成。"""

    async def prepare_for_new_subject(
        self,
        *,
        user_id: int,
        subject: str,
        goal: str | None,
        goal_priorities: list[str] | None,
        level: str,
        session: AsyncSession,
    ) -> None:
        """新建内容后重置该用户在此内容上的学习起点。"""
        priorities = normalize_goal_priorities(goal_priorities, goal)
        goal_text = format_goal_text(priorities)
        await learning_content_access_service.register_subject(
            user_id=user_id,
            subject=subject,
            session=session,
        )
        await self._reset_user_subject_data(
            user_id=user_id,
            subject=subject,
            session=session,
        )
        session.add(
            InitialDiagnosis(
                user_id=user_id,
                subject=subject,
                learning_goal=goal_text,
                level=level,
                status="pending",
                result={"goal_priorities": priorities},
            )
        )
        await session.commit()

    async def get_status(
        self,
        *,
        user_id: int,
        subject: str,
        session: AsyncSession,
    ) -> InitialDiagnosisStatusData:
        """返回当前用户是否需要并已完成初始诊断。"""
        await learning_content_access_service.ensure_access(
            user_id=user_id,
            subject=subject,
            session=session,
        )
        graph = await knowledge_service.get_graph(subject)
        required = await self._is_generated_subject(subject)
        if not required:
            return InitialDiagnosisStatusData(
                subject=graph.subject,
                title=graph.title,
                required=False,
                completed=True,
            )

        diagnosis = await self._find_latest(
            user_id=user_id,
            subject=subject,
            session=session,
        )
        return InitialDiagnosisStatusData(
            subject=graph.subject,
            title=graph.title,
            required=True,
            completed=diagnosis is not None
            and diagnosis.status == "completed",
            session_id=diagnosis.id if diagnosis is not None else None,
            learning_goal=(
                diagnosis.learning_goal
                if diagnosis is not None
                else DEFAULT_GOAL
            ),
            level=diagnosis.level if diagnosis is not None else "基础",
        )

    async def start(
        self,
        *,
        user_id: int,
        subject: str,
        goal: str | None,
        level: str | None,
        session: AsyncSession,
    ) -> StartInitialDiagnosisData:
        """创建或恢复初始诊断，并随机准备跨模块题目。"""
        await learning_content_access_service.ensure_access(
            user_id=user_id,
            subject=subject,
            session=session,
        )
        graph = await knowledge_service.get_graph(subject)
        if not await self._is_generated_subject(subject):
            raise InitialDiagnosisStateError("非用户生成的学习内容无需初始诊断")
        diagnosis = await self._find_latest(
            user_id=user_id,
            subject=subject,
            session=session,
        )
        if diagnosis is None:
            priorities = normalize_goal_priorities(None, goal)
            diagnosis = InitialDiagnosis(
                user_id=user_id,
                subject=graph.subject,
                learning_goal=format_goal_text(priorities),
                level=level or "基础",
                status="pending",
                result={"goal_priorities": priorities},
            )
            session.add(diagnosis)
            await session.flush()
        elif diagnosis.status != "pending":
            raise InitialDiagnosisStateError("该学习内容的初始诊断已完成")

        if diagnosis.questions:
            return StartInitialDiagnosisData(
                session_id=diagnosis.id,
                subject=graph.subject,
                title=graph.title,
                learning_goal=diagnosis.learning_goal,
                level=diagnosis.level,
                questions=diagnosis.questions,
            )

        questions = await self._generate_questions(
            graph,
            diagnosis.learning_goal,
        )
        if len(questions) < MIN_DIAGNOSIS_QUESTIONS:
            raise InitialDiagnosisUnavailableError(
                "当前内容可用的初始诊断题目不足，请稍后重试"
            )

        diagnosis.questions = [
            question.model_dump(mode="json") for question in questions
        ]
        await session.commit()
        return StartInitialDiagnosisData(
            session_id=diagnosis.id,
            subject=graph.subject,
            title=graph.title,
            learning_goal=diagnosis.learning_goal,
            level=diagnosis.level,
            questions=questions,
        )

    async def complete(
        self,
        *,
        user_id: int,
        session_id: int,
        answers: list[InitialDiagnosisAnswer],
        session: AsyncSession,
    ) -> CompleteInitialDiagnosisData:
        """批改整套诊断、保存结果并生成个性化学习路径。"""
        diagnosis = await session.get(InitialDiagnosis, session_id)
        if diagnosis is None or diagnosis.user_id != user_id:
            raise InitialDiagnosisNotFoundError("初始诊断会话不存在")
        await learning_content_access_service.ensure_access(
            user_id=user_id,
            subject=diagnosis.subject,
            session=session,
        )
        if diagnosis.status == "completed":
            return await self._completed_result(user_id, diagnosis, session)
        if not diagnosis.questions:
            raise InitialDiagnosisStateError("初始诊断已提交或尚未开始")
        if await session.get(User, user_id) is None:
            raise InitialDiagnosisNotFoundError("用户不存在")

        expected_ids = [str(item["id"]) for item in diagnosis.questions]
        answer_ids = [item.question_id for item in answers]
        if (
            len(answer_ids) != len(set(answer_ids))
            or set(answer_ids) != set(expected_ids)
        ):
            raise InitialDiagnosisStateError("请完成全部初始诊断题目后再提交")

        try:
            graded = await practice_service.submit_answers(
                user_id=user_id,
                answers=[
                    (
                        item.question_id,
                        item.answer,
                        item.time_spent,
                    )
                    for item in answers
                ],
                session=session,
                commit=False,
            )
        except PracticeNotFoundError as exc:
            raise InitialDiagnosisStateError(str(exc)) from exc

        correct_count = sum(1 for item in graded if item.is_correct)
        answered_count = len(graded)
        accuracy = correct_count / answered_count
        graph = await knowledge_service.get_graph(diagnosis.subject)
        mastery_map = await self._load_mastery_map(
            user_id=user_id,
            subject=diagnosis.subject,
            session=session,
        )
        goal_priorities = self._goal_priorities_from_diagnosis(diagnosis)
        steps, path_summary = self._build_personalized_path(
            graph=graph,
            mastery_map=mastery_map,
            goal=diagnosis.learning_goal,
            goal_priorities=goal_priorities,
            accuracy=accuracy,
        )
        await diagnosis_history_service.save_initial_snapshot(
            user_id=user_id,
            subject=diagnosis.subject,
            diagnosis_id=diagnosis.id,
            mastery_map=mastery_map,
            answered_count=answered_count,
            correct_count=correct_count,
            session=session,
        )
        await self._save_learning_path(
            user_id=user_id,
            subject=diagnosis.subject,
            goal=diagnosis.learning_goal,
            goal_priorities=goal_priorities,
            level=diagnosis.level,
            accuracy=accuracy,
            correct_count=correct_count,
            answered_count=answered_count,
            path_summary=path_summary,
            steps=steps,
            session=session,
        )

        diagnosis.status = "completed"
        diagnosis.result = {
            "answered_count": answered_count,
            "correct_count": correct_count,
            "accuracy": round(accuracy, 4),
            "path_summary": path_summary,
            "goal_priorities": goal_priorities,
        }
        diagnosis.completed_at = datetime.now(UTC)
        await session.commit()

        analysis = await adaptive_engine.analyze(
            user_id,
            session,
            subject=diagnosis.subject,
        )
        progress = await adaptive_engine.get_progress(
            user_id,
            session,
            subject=diagnosis.subject,
        )
        return CompleteInitialDiagnosisData(
            session_id=diagnosis.id,
            subject=diagnosis.subject,
            learning_goal=diagnosis.learning_goal,
            answered_count=answered_count,
            correct_count=correct_count,
            accuracy=round(accuracy, 4),
            path_summary=path_summary,
            analysis=analysis,
            progress=progress,
        )

    @staticmethod
    async def _completed_result(
        user_id: int,
        diagnosis: InitialDiagnosis,
        session: AsyncSession,
    ) -> CompleteInitialDiagnosisData:
        """重复提交时返回已保存的诊断与个性化路径。"""
        stored = diagnosis.result or {}
        analysis = await adaptive_engine.analyze(
            user_id,
            session,
            subject=diagnosis.subject,
        )
        progress = await adaptive_engine.get_progress(
            user_id,
            session,
            subject=diagnosis.subject,
        )
        return CompleteInitialDiagnosisData(
            session_id=diagnosis.id,
            subject=diagnosis.subject,
            learning_goal=diagnosis.learning_goal,
            answered_count=int(stored.get("answered_count", len(progress.points))),
            correct_count=int(stored.get("correct_count", 0)),
            accuracy=float(stored.get("accuracy", 0.0)),
            path_summary=str(stored.get("path_summary", "")),
            analysis=analysis,
            progress=progress,
        )

    async def _generate_questions(
        self,
        graph: KnowledgeGraphData,
        goal: str,
    ) -> list[Any]:
        """随机选择不同模块的知识点并生成初始诊断题。"""
        point_ids = self._select_diagnosis_points(graph.nodes, goal)
        responses = await asyncio.gather(
            *(
                practice_service.get_questions(
                    point_id,
                    count=QUESTIONS_PER_POINT,
                    learning_goal=goal,
                )
                for point_id in point_ids
            ),
            return_exceptions=True,
        )
        questions = []
        seen_ids: set[str] = set()
        for response in responses:
            if isinstance(response, Exception):
                continue
            for question in response.questions:
                if question.id in seen_ids:
                    continue
                seen_ids.add(question.id)
                questions.append(question)
        random.shuffle(questions)
        return questions[:10]

    @staticmethod
    def _select_diagnosis_points(
        nodes: list[KnowledgePointNode],
        goal: str,
    ) -> list[str]:
        """按模块分层抽样，并让与学习目标相关的内容优先进入样本。"""
        if not nodes:
            return []

        goal_terms = [
            term
            for term in re.split(r"[、,，;；\s]+", goal)
            if len(term) >= 2
        ]
        grouped: dict[str, list[KnowledgePointNode]] = {}
        for node in nodes:
            grouped.setdefault(node.category, []).append(node)

        categories = list(grouped)
        random.shuffle(categories)
        selected: list[KnowledgePointNode] = []
        while categories and len(selected) < DIAGNOSIS_POINT_COUNT:
            category = categories.pop()
            candidates = grouped[category]
            preferred = [
                node
                for node in candidates
                if any(
                    term
                    in f"{node.name}{node.category}{''.join(node.tags)}"
                    for term in goal_terms
                )
            ]
            selected.append(random.choice(preferred or candidates))

        remaining = [node for node in nodes if node not in selected]
        random.shuffle(remaining)
        selected.extend(remaining[: DIAGNOSIS_POINT_COUNT - len(selected)])
        return [node.id for node in selected]

    @staticmethod
    async def _load_mastery_map(
        *,
        user_id: int,
        subject: str,
        session: AsyncSession,
    ) -> dict[str, float]:
        """读取初始诊断后各知识点的掌握度。"""
        from app.services.knowledge_tracer import knowledge_tracer

        breakdowns = await knowledge_tracer.calculate_mastery_map(
            user_id,
            session,
            subject=subject,
        )
        return {
            point_id: breakdown.mastery
            for point_id, breakdown in breakdowns.items()
        }

    def _build_personalized_path(
        self,
        *,
        graph: KnowledgeGraphData,
        mastery_map: dict[str, float],
        goal: str,
        goal_priorities: list[str],
        accuracy: float,
    ) -> tuple[list[LearningPathStep], str]:
        """根据目标、诊断表现和先修关系生成有序个性化路径。"""
        selected_ids: set[str] = set()
        steps: list[LearningPathStep] = []
        expected_difficulty = self._expected_difficulty(accuracy)
        goal_scores = {
            node.id: goal_affinity(node, goal_priorities)
            for node in graph.nodes
        }

        for step_number in range(1, MAX_PERSONALIZED_PATH_STEPS + 1):
            candidates: list[tuple[float, KnowledgePointNode]] = []
            for node in graph.nodes:
                mastery = mastery_map.get(node.id, 0.0)
                if node.id in selected_ids or mastery >= MASTERED_THRESHOLD:
                    continue
                if not all(
                    mastery_map.get(prerequisite, 0.0) >= 0.7
                    or prerequisite in selected_ids
                    for prerequisite in node.prerequisites
                ):
                    continue
                difficulty_fit = 1.0 - min(
                    abs(node.difficulty - expected_difficulty) / 4,
                    1.0,
                )
                score = (
                    (1.0 - mastery) * 0.5
                    + goal_scores[node.id] * 0.32
                    + difficulty_fit * 0.18
                )
                candidates.append((score, node))

            if not candidates:
                break
            candidates.sort(
                key=lambda item: (
                    -item[0],
                    item[1].difficulty,
                    item[1].id,
                )
            )
            selected = candidates[0][1]
            selected_ids.add(selected.id)
            steps.append(
                LearningPathStep(
                    step=step_number,
                    knowledge_point_id=selected.id,
                    name=selected.name,
                    difficulty=selected.difficulty,
                    estimated_time=ESTIMATED_LEARNING_MINUTES.get(
                        selected.difficulty,
                        ESTIMATED_LEARNING_MINUTES[5],
                    ),
                )
            )

        nodes_by_id = {node.id: node for node in graph.nodes}
        path_categories: list[str] = []
        for step in steps:
            node = nodes_by_id.get(step.knowledge_point_id)
            if (
                node is not None
                and node.category not in path_categories
            ):
                path_categories.append(node.category)
            if len(path_categories) >= 3:
                break

        weak_categories = []
        for point_id, mastery in sorted(
            mastery_map.items(),
            key=lambda item: item[1],
        ):
            node = nodes_by_id.get(point_id)
            if node is None or mastery >= 0.55:
                continue
            if node.category not in weak_categories:
                weak_categories.append(node.category)
            if len(weak_categories) >= 3:
                break

        focus = (
            "、".join(path_categories)
            if path_categories
            else (
                "、".join(weak_categories)
                if weak_categories
                else "核心知识模块"
            )
        )
        path_summary = (
            "按照学习目标优先级"
            f"“{format_goal_priority_text(goal_priorities)}”"
            f"优先安排{focus}相关内容，"
            f"并结合本次诊断正确率 {round(accuracy * 100)}% "
            "安排由浅入深的学习顺序。"
        )
        return steps, path_summary

    @staticmethod
    def _expected_difficulty(accuracy: float) -> int:
        """按诊断正确率估算当前最适合的知识点难度。"""
        if accuracy < 0.35:
            return 1
        if accuracy < 0.6:
            return 2
        if accuracy < 0.8:
            return 3
        if accuracy < 0.95:
            return 4
        return 5

    async def _save_learning_path(
        self,
        *,
        user_id: int,
        subject: str,
        goal: str,
        goal_priorities: list[str],
        level: str,
        accuracy: float,
        correct_count: int,
        answered_count: int,
        path_summary: str,
        steps: list[LearningPathStep],
        session: AsyncSession,
    ) -> None:
        """停用旧路径并保存本次诊断生成的个性化路径。"""
        await session.execute(
            update(LearningPath)
            .where(
                LearningPath.user_id == user_id,
                LearningPath.subject == subject,
                LearningPath.is_active.is_(True),
            )
            .values(is_active=False)
        )
        session.add(
            LearningPath(
                user_id=user_id,
                subject=subject,
                path_data={
                    "version": "personalized-1.1.0",
                    "learning_goal": goal,
                    "goal_priorities": goal_priorities,
                    "level": level,
                    "diagnosis": {
                        "answered_count": answered_count,
                        "correct_count": correct_count,
                        "accuracy": round(accuracy, 4),
                    },
                    "path_summary": path_summary,
                    "steps": [
                        step.model_dump(mode="json") for step in steps
                    ],
                },
                is_active=True,
            )
        )
        await session.flush()

    @staticmethod
    def _goal_priorities_from_diagnosis(
        diagnosis: InitialDiagnosis,
    ) -> list[str]:
        """从新诊断结果或旧版目标字符串恢复优先顺序。"""
        stored = diagnosis.result if isinstance(diagnosis.result, dict) else {}
        raw_priorities = stored.get("goal_priorities")
        priorities = (
            [str(item) for item in raw_priorities]
            if isinstance(raw_priorities, list)
            else None
        )
        return normalize_goal_priorities(
            priorities,
            diagnosis.learning_goal,
        )

    @staticmethod
    async def _reset_user_subject_data(
        *,
        user_id: int,
        subject: str,
        session: AsyncSession,
    ) -> None:
        """重新生成同一内容时清理该用户旧的起点数据。"""
        for model in (
            AttemptRecord,
            DiagnosisSnapshot,
            ErrorBook,
            InitialDiagnosis,
            LearningPath,
            LearningRecord,
        ):
            await session.execute(
                delete(model).where(
                    model.user_id == user_id,
                    model.subject == subject,
                )
            )

    @staticmethod
    async def _find_latest(
        *,
        user_id: int,
        subject: str,
        session: AsyncSession,
    ) -> InitialDiagnosis | None:
        """返回用户最近一次初始诊断记录。"""
        return await session.scalar(
            select(InitialDiagnosis)
            .where(
                InitialDiagnosis.user_id == user_id,
                InitialDiagnosis.subject == subject,
            )
            .order_by(InitialDiagnosis.created_at.desc())
            .limit(1)
        )

    @staticmethod
    async def _is_generated_subject(subject: str) -> bool:
        """判断学习内容是否由模型生成。"""
        try:
            await knowledge_service.get_generated_subject(subject)
        except SubjectNotDeletableError:
            return False
        return True


initial_diagnosis_service = InitialDiagnosisService()
