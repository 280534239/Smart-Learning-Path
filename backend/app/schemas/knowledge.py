"""知识图谱相关 Schema。"""

from typing import Literal

from pydantic import BaseModel, Field, field_validator


class LearningResource(BaseModel):
    """知识点关联的学习资源。"""

    type: str
    title: str
    url: str


class DetailedLearningResource(LearningResource):
    """包含完整知识讲解的学习资源。"""

    content: str = Field(min_length=200, max_length=12000)


class KnowledgePointResources(BaseModel):
    """知识点按需生成的学习资源集合。"""

    point_id: str
    point_name: str
    resources: list[DetailedLearningResource]


class KnowledgeEdge(BaseModel):
    """知识图谱原始边数据。"""

    source: str
    target: str
    relation: str = "prerequisite"


class GraphEdge(BaseModel):
    """面向可视化接口的边数据。"""

    source: str = Field(serialization_alias="from")
    target: str = Field(serialization_alias="to")
    relation: str = "prerequisite"


class KnowledgePointNode(BaseModel):
    """知识图谱中的完整知识点节点。"""

    id: str
    name: str
    description: str
    category: str
    difficulty: int = Field(ge=1, le=5)
    prerequisites: list[str]
    resources: list[LearningResource]
    tags: list[str]


class KnowledgeGraphDocument(BaseModel):
    """知识图谱 JSON 文件的根结构。"""

    subject: str
    version: str
    description: str
    node_count: int
    edge_count: int
    nodes: list[KnowledgePointNode]
    edges: list[KnowledgeEdge]


class KnowledgeGraphData(BaseModel):
    """知识图谱可视化接口数据。"""

    subject: str
    title: str
    version: str
    nodes: list[KnowledgePointNode]
    edges: list[GraphEdge]


class KnowledgePointRef(BaseModel):
    """知识点关联关系中的精简信息。"""

    id: str
    name: str
    category: str
    difficulty: int = Field(ge=1, le=5)


class KnowledgePointDetail(BaseModel):
    """单个知识点及其前后依赖详情。"""

    id: str
    name: str
    description: str
    category: str
    difficulty: int = Field(ge=1, le=5)
    tags: list[str]
    resources: list[LearningResource]
    prerequisites: list[KnowledgePointRef]
    successors: list[KnowledgePointRef]


class CategoryStat(BaseModel):
    """分类模块统计。"""

    name: str
    count: int = Field(ge=0)
    difficulty_min: int = Field(ge=1, le=5)
    difficulty_max: int = Field(ge=1, le=5)


class CategoryGraphData(BaseModel):
    """知识图谱分类统计接口数据。"""

    subject: str
    title: str
    total: int = Field(ge=0)
    categories: list[CategoryStat]


class SubjectSummary(BaseModel):
    """可选学习内容的摘要信息。"""

    subject: str
    title: str
    description: str
    node_count: int = Field(ge=0)
    generated: bool = False


class SubjectListData(BaseModel):
    """当前可切换的学习内容列表。"""

    default_subject: str
    subjects: list[SubjectSummary]


class SubjectDeletionData(BaseModel):
    """学习内容及其关联数据的删除结果。"""

    subject: str
    title: str
    deleted_records: dict[str, int]
    total_deleted_records: int = Field(ge=0)


class GenerateSubjectRequest(BaseModel):
    """通过模型生成新学习内容的请求。"""

    topic: str = Field(min_length=2, max_length=100)
    goal: str | None = Field(default=None, max_length=500)
    goal_priorities: list[str] = Field(
        default_factory=list,
        max_length=8,
    )
    level: Literal["入门", "基础", "进阶", "高级"] = "基础"

    @field_validator("topic")
    @classmethod
    def normalize_topic(cls, value: str) -> str:
        """去除主题首尾空白并确保仍有足够内容。"""
        normalized = value.strip()
        if len(normalized) < 2:
            raise ValueError("学习主题至少需要 2 个字符")
        return normalized

    @field_validator("goal_priorities")
    @classmethod
    def normalize_goal_priority_values(cls, values: list[str]) -> list[str]:
        """清理目标标签并去重，保留用户设置的优先顺序。"""
        normalized: list[str] = []
        for value in values:
            item = value.strip()
            if not item or item in normalized:
                continue
            normalized.append(item[:40])
        return normalized
