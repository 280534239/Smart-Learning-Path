"""知识图谱加载、校验与内存查询服务。"""

import asyncio
import json
import logging
from collections import deque
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app.schemas.knowledge import (
    CategoryGraphData,
    CategoryStat,
    GraphEdge,
    KnowledgeGraphData,
    KnowledgeGraphDocument,
    KnowledgePointDetail,
    KnowledgePointNode,
    KnowledgePointRef,
    SubjectListData,
    SubjectSummary,
)

GENERATED_GRAPH_DIR = (
    Path(__file__).resolve().parents[2] / "data" / "generated_subjects"
)

logger = logging.getLogger(__name__)


class KnowledgeGraphError(Exception):
    """知识图谱业务异常基类。"""


class SubjectNotFoundError(KnowledgeGraphError):
    """请求的学科不存在。"""


class SubjectNotDeletableError(KnowledgeGraphError):
    """学习内容不是由用户生成，不允许删除。"""


class KnowledgePointNotFoundError(KnowledgeGraphError):
    """请求的知识点不存在。"""


@dataclass(frozen=True, slots=True)
class LoadedKnowledgeGraph:
    """预计算后的内存知识图谱。"""

    subject: str
    title: str
    description: str
    version: str
    generated: bool
    nodes: tuple[KnowledgePointNode, ...]
    edges: tuple[GraphEdge, ...]
    node_by_id: dict[str, KnowledgePointNode]
    successor_ids: dict[str, tuple[str, ...]]


class KnowledgeGraphService:
    """管理知识图谱文件加载和内存查询。"""

    def __init__(self) -> None:
        self._graphs: dict[str, LoadedKnowledgeGraph] = {}
        self._point_index: dict[str, tuple[str, KnowledgePointNode]] = {}
        self._loaded = False
        self._load_lock = asyncio.Lock()

    async def load_all(self, *, force: bool = False) -> None:
        """加载并校验全部学科图谱，应用启动时调用一次。"""
        async with self._load_lock:
            if self._loaded and not force:
                return

            loaded_graphs: dict[str, LoadedKnowledgeGraph] = {}
            for subject, source in self._discover_generated_sources().items():
                try:
                    graph = await asyncio.to_thread(
                        self._load_subject,
                        subject,
                        source,
                        True,
                    )
                except Exception:
                    logger.exception(
                        "跳过无法加载的生成内容: %s",
                        source,
                    )
                    continue
                loaded_graphs[subject] = graph

            point_index: dict[str, tuple[str, KnowledgePointNode]] = {}
            for subject, graph in loaded_graphs.items():
                for node in graph.nodes:
                    if node.id in point_index:
                        raise ValueError(f"知识点 ID 跨学科重复: {node.id}")
                    point_index[node.id] = (subject, node)

            self._graphs = loaded_graphs
            self._point_index = point_index
            self._loaded = True

    async def _ensure_loaded(self) -> None:
        """确保服务已加载知识图谱。"""
        if not self._loaded:
            await self.load_all()

    def _load_subject(
        self,
        subject: str,
        source: Path,
        generated: bool,
    ) -> LoadedKnowledgeGraph:
        """从 JSON 文件加载并构建单个学科的内存索引。"""
        raw_data: dict[str, Any] = json.loads(
            source.read_text(encoding="utf-8")
        )
        document = KnowledgeGraphDocument.model_validate(raw_data)
        self.validate_document(document)

        nodes = tuple(document.nodes)
        edges = tuple(
            GraphEdge(
                source=edge.source,
                target=edge.target,
                relation=edge.relation,
            )
            for edge in document.edges
        )
        node_by_id = {node.id: node for node in nodes}
        successor_ids = self._build_successor_index(nodes)

        return LoadedKnowledgeGraph(
            subject=subject,
            title=document.subject,
            description=document.description,
            version=document.version,
            generated=generated,
            nodes=nodes,
            edges=edges,
            node_by_id=node_by_id,
            successor_ids=successor_ids,
        )

    @staticmethod
    def _discover_generated_sources() -> dict[str, Path]:
        """扫描运行时生成的学科图谱文件。"""
        if not GENERATED_GRAPH_DIR.exists():
            return {}
        return {
            path.stem: path
            for path in sorted(GENERATED_GRAPH_DIR.glob("*.json"))
            if path.is_file()
        }

    @staticmethod
    def validate_document(document: KnowledgeGraphDocument) -> None:
        """校验计数、节点关联关系及 DAG 无环性。"""
        if document.node_count != len(document.nodes):
            raise ValueError("知识图谱 node_count 与实际节点数不一致")
        if document.edge_count != len(document.edges):
            raise ValueError("知识图谱 edge_count 与实际边数不一致")

        node_by_id = {node.id: node for node in document.nodes}
        if len(node_by_id) != len(document.nodes):
            raise ValueError("知识图谱存在重复节点 ID")
        if any(
            len(node.prerequisites) != len(set(node.prerequisites))
            for node in document.nodes
        ):
            raise ValueError("知识点存在重复前置依赖")
        if any(
            edge.relation != "prerequisite"
            for edge in document.edges
        ):
            raise ValueError("知识图谱存在不支持的关系类型")

        expected_edges = {
            (prerequisite, node.id)
            for node in document.nodes
            for prerequisite in node.prerequisites
        }
        actual_edges = {
            (edge.source, edge.target)
            for edge in document.edges
        }
        if len(actual_edges) != len(document.edges):
            raise ValueError("知识图谱存在重复边")
        if actual_edges != expected_edges:
            raise ValueError("知识图谱边与节点前置依赖不一致")

        indegree = {node_id: 0 for node_id in node_by_id}
        outgoing: dict[str, list[str]] = {
            node_id: [] for node_id in node_by_id
        }
        for source, target in actual_edges:
            if source not in node_by_id or target not in node_by_id:
                raise ValueError("知识图谱边引用了不存在的节点")
            indegree[target] += 1
            outgoing[source].append(target)

        queue = deque(
            node_id
            for node_id, degree in indegree.items()
            if degree == 0
        )
        visited = 0
        while queue:
            node_id = queue.popleft()
            visited += 1
            for target in outgoing[node_id]:
                indegree[target] -= 1
                if indegree[target] == 0:
                    queue.append(target)

        if visited != len(document.nodes):
            raise ValueError("知识图谱中存在循环依赖")

    @staticmethod
    def _build_successor_index(
        nodes: tuple[KnowledgePointNode, ...],
    ) -> dict[str, tuple[str, ...]]:
        """根据前置依赖关系构建后继知识点索引。"""
        successors: dict[str, list[str]] = {
            node.id: [] for node in nodes
        }
        for node in nodes:
            for prerequisite in node.prerequisites:
                successors[prerequisite].append(node.id)
        return {
            node_id: tuple(targets)
            for node_id, targets in successors.items()
        }

    @staticmethod
    def _normalize_subject(subject: str) -> str:
        """规范化学科路径参数。"""
        return subject.strip().lower()

    async def _get_graph(self, subject: str) -> LoadedKnowledgeGraph:
        """返回指定学科内存图谱，不存在时抛出业务异常。"""
        await self._ensure_loaded()
        graph = self._graphs.get(self._normalize_subject(subject))
        if graph is None:
            raise SubjectNotFoundError(f"未找到学科: {subject}")
        return graph

    async def get_graph(self, subject: str) -> KnowledgeGraphData:
        """返回指定学科的完整节点与边。"""
        graph = await self._get_graph(subject)
        return KnowledgeGraphData(
            subject=graph.subject,
            title=graph.title,
            version=graph.version,
            nodes=list(graph.nodes),
            edges=list(graph.edges),
        )

    async def get_generated_subject(self, subject: str) -> LoadedKnowledgeGraph:
        """返回可删除的模型生成学习内容。"""
        graph = await self._get_graph(subject)
        if not graph.generated:
            raise SubjectNotDeletableError("非用户生成的学习内容不可删除")
        return graph

    async def list_subjects(self) -> SubjectListData:
        """返回全部模型生成的学习内容。"""
        await self._ensure_loaded()
        summaries = [
            SubjectSummary(
                subject=graph.subject,
                title=graph.title,
                description=graph.description,
                node_count=len(graph.nodes),
                generated=graph.generated,
            )
            for graph in self._graphs.values()
        ]
        summaries.sort(key=lambda item: item.title)
        return SubjectListData(
            default_subject=summaries[0].subject if summaries else "",
            subjects=summaries,
        )

    async def get_subject_point_map(self) -> dict[str, str]:
        """返回全部知识点 ID 到学习内容标识的映射。"""
        await self._ensure_loaded()
        return {
            point_id: subject
            for point_id, (subject, _) in self._point_index.items()
        }

    async def get_point_subject(self, kp_id: str) -> str:
        """返回知识点所属的学习内容标识。"""
        await self._ensure_loaded()
        indexed_point = self._point_index.get(kp_id)
        if indexed_point is None:
            raise KnowledgePointNotFoundError(f"未找到知识点: {kp_id}")
        return indexed_point[0]

    async def get_point(self, kp_id: str) -> KnowledgePointDetail:
        """返回知识点详情及直接前置、后继知识点。"""
        await self._ensure_loaded()
        indexed_point = self._point_index.get(kp_id)
        if indexed_point is None:
            raise KnowledgePointNotFoundError(f"未找到知识点: {kp_id}")

        subject, node = indexed_point
        graph = self._graphs[subject]
        prerequisite_points = [
            self._to_point_ref(graph.node_by_id[point_id])
            for point_id in node.prerequisites
        ]
        successor_points = [
            self._to_point_ref(graph.node_by_id[point_id])
            for point_id in graph.successor_ids[node.id]
        ]

        return KnowledgePointDetail(
            id=node.id,
            name=node.name,
            description=node.description,
            category=node.category,
            difficulty=node.difficulty,
            tags=list(node.tags),
            resources=list(node.resources),
            prerequisites=prerequisite_points,
            successors=successor_points,
        )

    async def get_categories(self, subject: str) -> CategoryGraphData:
        """返回学科分类模块及知识点数量统计。"""
        graph = await self._get_graph(subject)
        category_stats: dict[str, dict[str, int]] = {}
        for node in graph.nodes:
            stats = category_stats.setdefault(
                node.category,
                {
                    "count": 0,
                    "difficulty_min": node.difficulty,
                    "difficulty_max": node.difficulty,
                },
            )
            stats["count"] += 1
            stats["difficulty_min"] = min(
                stats["difficulty_min"],
                node.difficulty,
            )
            stats["difficulty_max"] = max(
                stats["difficulty_max"],
                node.difficulty,
            )

        categories = [
            CategoryStat(
                name=name,
                count=stats["count"],
                difficulty_min=stats["difficulty_min"],
                difficulty_max=stats["difficulty_max"],
            )
            for name, stats in category_stats.items()
        ]
        return CategoryGraphData(
            subject=graph.subject,
            title=graph.title,
            total=len(graph.nodes),
            categories=categories,
        )

    @staticmethod
    def _to_point_ref(node: KnowledgePointNode) -> KnowledgePointRef:
        """将完整节点压缩为关联关系摘要。"""
        return KnowledgePointRef(
            id=node.id,
            name=node.name,
            category=node.category,
            difficulty=node.difficulty,
        )


knowledge_service = KnowledgeGraphService()
