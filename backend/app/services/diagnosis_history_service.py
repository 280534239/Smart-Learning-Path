"""历次诊断快照的记录与查询。"""

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.diagnosis_snapshot import DiagnosisSnapshot
from app.models.initial_diagnosis import InitialDiagnosis
from app.schemas.diagnosis_snapshot import (
    DiagnosisSnapshotData,
    DiagnosisSnapshotListData,
)
from app.schemas.knowledge import KnowledgePointNode
from app.services.knowledge_service import knowledge_service
from app.services.knowledge_tracer import knowledge_tracer
from app.services.learning_content_access_service import (
    learning_content_access_service,
)


class DiagnosisHistoryService:
    """保存诊断时刻的模块掌握度，供雷达图对比。"""

    async def save_initial_snapshot(
        self,
        *,
        user_id: int,
        subject: str,
        diagnosis_id: int,
        mastery_map: dict[str, float],
        answered_count: int,
        correct_count: int,
        session: AsyncSession,
    ) -> None:
        """在初始诊断事务中保存第一条雷达数据。"""
        reference_id = f"initial-{diagnosis_id}"
        existing = await self._find_by_reference(
            user_id=user_id,
            subject=subject,
            reference_id=reference_id,
            session=session,
        )
        if existing is not None:
            return

        graph = await knowledge_service.get_graph(subject)
        category_mastery = self._category_mastery(
            graph.nodes,
            mastery_map,
        )
        overall = self._overall_mastery(mastery_map)
        session.add(
            DiagnosisSnapshot(
                user_id=user_id,
                subject=subject,
                source="initial",
                reference_id=reference_id,
                label="初始诊断",
                category_mastery=category_mastery,
                overall_mastery=overall,
                answered_count=answered_count,
                correct_count=correct_count,
            )
        )
        await session.flush()

    async def record_smart_diagnosis(
        self,
        *,
        user_id: int,
        subject: str,
        reference_id: str,
        session: AsyncSession,
    ) -> DiagnosisSnapshotData:
        """完成一次智能诊断后记录当前掌握度快照。"""
        await learning_content_access_service.ensure_access(
            user_id=user_id,
            subject=subject,
            session=session,
        )
        existing = await self._find_by_reference(
            user_id=user_id,
            subject=subject,
            reference_id=reference_id,
            session=session,
        )
        if existing is not None:
            return self._to_data(existing)

        mastery_breakdown = await knowledge_tracer.calculate_mastery_map(
            user_id,
            session,
            subject=subject,
        )
        mastery_map = {
            point_id: breakdown.mastery
            for point_id, breakdown in mastery_breakdown.items()
        }
        graph = await knowledge_service.get_graph(subject)
        previous_count = await session.scalar(
            select(func.count(DiagnosisSnapshot.id)).where(
                DiagnosisSnapshot.user_id == user_id,
                DiagnosisSnapshot.subject == subject,
                DiagnosisSnapshot.source == "smart",
            )
        )
        snapshot = DiagnosisSnapshot(
            user_id=user_id,
            subject=subject,
            source="smart",
            reference_id=reference_id,
            label=f"智能诊断 {int(previous_count or 0) + 1}",
            category_mastery=self._category_mastery(
                graph.nodes,
                mastery_map,
            ),
            overall_mastery=self._overall_mastery(mastery_map),
            answered_count=0,
            correct_count=0,
        )
        session.add(snapshot)
        await session.commit()
        await session.refresh(snapshot)
        return self._to_data(snapshot)

    async def list_snapshots(
        self,
        *,
        user_id: int,
        subject: str,
        session: AsyncSession,
    ) -> DiagnosisSnapshotListData:
        """返回指定学习内容按时间排列的全部诊断快照。"""
        await learning_content_access_service.ensure_access(
            user_id=user_id,
            subject=subject,
            session=session,
        )
        graph = await knowledge_service.get_graph(subject)
        await self._ensure_initial_snapshot(
            user_id=user_id,
            subject=subject,
            graph_nodes=graph.nodes,
            session=session,
        )
        snapshots = (
            await session.scalars(
                select(DiagnosisSnapshot)
                .where(
                    DiagnosisSnapshot.user_id == user_id,
                    DiagnosisSnapshot.subject == subject,
                )
                .order_by(
                    DiagnosisSnapshot.created_at.asc(),
                    DiagnosisSnapshot.id.asc(),
                )
            )
        ).all()
        return DiagnosisSnapshotListData(
            subject=graph.subject,
            categories=list(
                dict.fromkeys(node.category for node in graph.nodes)
            ),
            snapshots=[self._to_data(item) for item in snapshots],
        )

    async def _ensure_initial_snapshot(
        self,
        *,
        user_id: int,
        subject: str,
        graph_nodes: list[KnowledgePointNode],
        session: AsyncSession,
    ) -> None:
        """为升级前已完成初始诊断的用户补建第一条快照。"""
        existing_initial = await session.scalar(
            select(DiagnosisSnapshot.id)
            .where(
                DiagnosisSnapshot.user_id == user_id,
                DiagnosisSnapshot.subject == subject,
                DiagnosisSnapshot.source == "initial",
            )
            .limit(1)
        )
        if existing_initial is not None:
            return
        diagnosis = await session.scalar(
            select(InitialDiagnosis)
            .where(
                InitialDiagnosis.user_id == user_id,
                InitialDiagnosis.subject == subject,
                InitialDiagnosis.status == "completed",
            )
            .order_by(InitialDiagnosis.completed_at.desc())
            .limit(1)
        )
        if diagnosis is None:
            return

        breakdowns = await knowledge_tracer.calculate_mastery_map(
            user_id,
            session,
            subject=subject,
        )
        mastery_map = {
            point_id: breakdown.mastery
            for point_id, breakdown in breakdowns.items()
        }
        result = diagnosis.result or {}
        session.add(
            DiagnosisSnapshot(
                user_id=user_id,
                subject=subject,
                source="initial",
                reference_id=f"initial-{diagnosis.id}",
                label="初始诊断",
                category_mastery=self._category_mastery(
                    graph_nodes,
                    mastery_map,
                ),
                overall_mastery=self._overall_mastery(mastery_map),
                answered_count=int(result.get("answered_count", 0)),
                correct_count=int(result.get("correct_count", 0)),
                created_at=diagnosis.completed_at or diagnosis.created_at,
            )
        )
        await session.commit()

    @staticmethod
    async def _find_by_reference(
        *,
        user_id: int,
        subject: str,
        reference_id: str,
        session: AsyncSession,
    ) -> DiagnosisSnapshot | None:
        """按幂等引用查找已保存的诊断。"""
        return await session.scalar(
            select(DiagnosisSnapshot).where(
                DiagnosisSnapshot.user_id == user_id,
                DiagnosisSnapshot.subject == subject,
                DiagnosisSnapshot.reference_id == reference_id,
            )
        )

    @staticmethod
    def _category_mastery(
        nodes: list[KnowledgePointNode],
        mastery_map: dict[str, float],
    ) -> dict[str, float]:
        """按知识模块计算平均掌握度。"""
        grouped: dict[str, list[float]] = {}
        for node in nodes:
            grouped.setdefault(node.category, []).append(
                mastery_map.get(node.id, 0.0)
            )
        return {
            category: round(
                sum(values) / len(values) if values else 0.0,
                4,
            )
            for category, values in grouped.items()
        }

    @staticmethod
    def _overall_mastery(mastery_map: dict[str, float]) -> float:
        """计算全部知识点的平均掌握度。"""
        if not mastery_map:
            return 0.0
        return round(
            sum(mastery_map.values()) / len(mastery_map),
            4,
        )

    @staticmethod
    def _to_data(snapshot: DiagnosisSnapshot) -> DiagnosisSnapshotData:
        """把数据库记录转换为前端雷达图数据。"""
        return DiagnosisSnapshotData(
            id=snapshot.id,
            subject=snapshot.subject,
            source=snapshot.source,
            label=snapshot.label,
            category_mastery={
                key: float(value)
                for key, value in snapshot.category_mastery.items()
            },
            overall_mastery=snapshot.overall_mastery,
            answered_count=snapshot.answered_count,
            correct_count=snapshot.correct_count,
            created_at=snapshot.created_at,
        )


diagnosis_history_service = DiagnosisHistoryService()
