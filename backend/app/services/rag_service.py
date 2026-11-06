"""ChromaDB 知识片段向量检索服务。"""

import asyncio
import logging
import math
import re
import unicodedata
from dataclasses import dataclass
from hashlib import blake2b
from pathlib import Path

import chromadb
from chromadb.api.types import Documents, EmbeddingFunction, Embeddings
from chromadb.config import Settings as ChromaSettings

from app.services.knowledge_service import knowledge_service
from app.services.practice_service import practice_service

CHROMA_DIR = (
    Path(__file__).resolve().parents[2] / "data" / "chroma"
)
COLLECTION_NAME = "knowledge_snippets_v2"
EMBEDDING_DIMENSION = 256
WORD_PATTERN = re.compile(r"[a-z0-9_]+")
CHINESE_PATTERN = re.compile(r"[\u4e00-\u9fff]")

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class IndexedDocument:
    """待写入 ChromaDB 的文档。"""

    id: str
    document: str
    metadata: dict[str, str]


@dataclass(frozen=True, slots=True)
class RAGChunk:
    """检索命中的知识片段。"""

    id: str
    document: str
    metadata: dict[str, str]
    score: float


class HashingEmbeddingFunction(
    EmbeddingFunction[Documents],
):
    """不依赖外部模型的本地哈希向量嵌入。"""

    def __init__(self, dimension: int = EMBEDDING_DIMENSION) -> None:
        self.dimension = dimension

    def __call__(self, input: Documents) -> Embeddings:
        """将文档转换为归一化的词与字符片段哈希向量。"""
        return [self._embed(document) for document in input]

    def name(self) -> str:
        """返回稳定的嵌入函数名称。"""
        return "smart-learning-hash-v1"

    def get_config(self) -> dict[str, int]:
        """返回可供 ChromaDB 持久化的配置。"""
        return {"dimension": self.dimension}

    @staticmethod
    def build_from_config(config: dict[str, int]) -> "HashingEmbeddingFunction":
        """根据持久化配置重建嵌入函数。"""
        return HashingEmbeddingFunction(
            dimension=config.get("dimension", EMBEDDING_DIMENSION)
        )

    def _embed(self, text: str) -> list[float]:
        """使用字符 n-gram 与英文词元生成稀疏哈希向量。"""
        vector = [0.0] * self.dimension
        normalized = unicodedata.normalize("NFKC", text).casefold()
        words = WORD_PATTERN.findall(normalized)
        chinese_characters = CHINESE_PATTERN.findall(normalized)
        chinese_bigrams = [
            "".join(chinese_characters[index:index + 2])
            for index in range(len(chinese_characters) - 1)
        ]

        features = [
            *(words * 2),
            *chinese_characters,
            *(chinese_bigrams * 2),
        ]
        for feature in features:
            digest = blake2b(
                feature.encode("utf-8"),
                digest_size=8,
            ).digest()
            index = int.from_bytes(digest[:4], "little") % self.dimension
            sign = 1.0 if digest[4] & 1 else -1.0
            vector[index] += sign

        norm = math.sqrt(sum(value * value for value in vector))
        if norm == 0:
            return vector
        return [value / norm for value in vector]


class RAGService:
    """管理知识片段索引与相关性检索。"""

    def __init__(self) -> None:
        self._client: chromadb.ClientAPI | None = None
        self._collection: chromadb.Collection | None = None
        self._ready = False
        self._init_lock = asyncio.Lock()
        self._indexed_subjects: frozenset[str] = frozenset()

    async def initialize(self, *, force: bool = False) -> None:
        """构建或刷新知识图谱、题目解析的向量索引。"""
        async with self._init_lock:
            if self._ready and not force:
                return

            documents = await self._build_documents()
            await asyncio.to_thread(self._initialize_sync, documents)
            self._indexed_subjects = frozenset(
                document.metadata["subject"]
                for document in documents
                if "subject" in document.metadata
            )
            self._ready = True

    async def _build_documents(self) -> list[IndexedDocument]:
        """从知识图谱和题库生成可检索文本。"""
        subject_list = await knowledge_service.list_subjects()
        point_subject_map = await knowledge_service.get_subject_point_map()
        questions = await practice_service.get_all_questions()
        documents: list[IndexedDocument] = []

        for summary in subject_list.subjects:
            graph = await knowledge_service.get_graph(summary.subject)
            for node in graph.nodes:
                tags = "、".join(node.tags)
                text = (
                    f"学习内容：{graph.title}\n"
                    f"知识点：{node.name}\n"
                    f"分类：{node.category}\n"
                    f"难度：{node.difficulty}\n"
                    f"描述：{node.description}\n"
                    f"标签：{tags}"
                )
                documents.append(
                    IndexedDocument(
                        id=f"knowledge:{node.id}",
                        document=text,
                        metadata={
                            "subject": graph.subject,
                            "source_type": "knowledge",
                            "source_id": node.id,
                            "knowledge_point_id": node.id,
                            "title": node.name,
                        },
                    )
                )

        for question in questions:
            subject = point_subject_map.get(question.knowledge_point_id)
            if subject is None:
                continue
            text = (
                f"知识点：{question.knowledge_point_id}\n"
                f"题目：{question.question}\n"
                f"题型：{question.type}\n"
                f"解析：{question.explanation}"
            )
            documents.append(
                IndexedDocument(
                    id=f"question:{question.id}",
                    document=text,
                    metadata={
                        "subject": subject,
                        "source_type": "question",
                        "source_id": question.id,
                        "knowledge_point_id": question.knowledge_point_id,
                        "title": question.question[:80],
                    },
                )
            )

        return documents

    def _initialize_sync(
        self,
        documents: list[IndexedDocument],
    ) -> None:
        """在线程中创建 ChromaDB 客户端并刷新集合。"""
        CHROMA_DIR.mkdir(parents=True, exist_ok=True)
        chroma_settings = ChromaSettings(
            anonymized_telemetry=False,
            allow_reset=True,
        )
        try:
            self._client = chromadb.PersistentClient(
                path=str(CHROMA_DIR),
                settings=chroma_settings,
            )
            collection, existing = self._prepare_collection(
                self._client,
                allow_recreate=True,
            )
        except Exception:
            logger.exception(
                "ChromaDB 持久化索引不可用，回退到内存索引"
            )
            self._client = chromadb.EphemeralClient(
                settings=chroma_settings
            )
            collection, existing = self._prepare_collection(
                self._client,
                allow_recreate=False,
            )

        self._collection = collection

        current_ids = {document.id for document in documents}
        stale_ids = set(existing.get("ids", [])) - current_ids
        if stale_ids:
            self._collection.delete(ids=sorted(stale_ids))

        if documents:
            self._collection.upsert(
                ids=[document.id for document in documents],
                documents=[
                    document.document for document in documents
                ],
                metadatas=[
                    document.metadata for document in documents
                ],
            )

    def _prepare_collection(
        self,
        client: chromadb.ClientAPI,
        *,
        allow_recreate: bool,
    ) -> tuple[chromadb.Collection, dict]:
        """打开集合并校验即可读取，必要时重建损坏索引。"""
        collection = client.get_or_create_collection(
            name=COLLECTION_NAME,
            embedding_function=HashingEmbeddingFunction(),
            metadata={"hnsw:space": "cosine"},
        )
        try:
            existing = collection.get(include=[])
        except Exception:
            if not allow_recreate:
                raise
            logger.warning("ChromaDB 集合损坏，正在重建: %s", COLLECTION_NAME)
            client.delete_collection(COLLECTION_NAME)
            collection = client.get_or_create_collection(
                name=COLLECTION_NAME,
                embedding_function=HashingEmbeddingFunction(),
                metadata={"hnsw:space": "cosine"},
            )
            existing = collection.get(include=[])
        return collection, existing

    async def _ensure_initialized(self) -> None:
        """确保向量索引已可用。"""
        if not self._ready:
            await self.initialize()

    async def close(self) -> None:
        """释放 ChromaDB 客户端引用。"""
        self._collection = None
        self._client = None
        self._ready = False
        self._indexed_subjects = frozenset()

    async def remove_subject(self, subject: str) -> None:
        """从向量索引中删除某个学习内容的全部片段。"""
        await self._ensure_initialized()
        if self._collection is None:
            return
        await asyncio.to_thread(
            self._collection.delete,
            where={"subject": subject},
        )
        self._indexed_subjects = self._indexed_subjects - {subject}

    async def retrieve(
        self,
        query: str,
        *,
        subject: str,
        knowledge_context: str | None = None,
        top_k: int = 4,
    ) -> list[RAGChunk]:
        """检索最相关的 3 到 5 个知识片段。"""
        await self._ensure_initialized()
        subject_list = await knowledge_service.list_subjects()
        current_subjects = frozenset(
            item.subject for item in subject_list.subjects
        )
        if current_subjects != self._indexed_subjects:
            await self.initialize(force=True)
        assert self._collection is not None
        if self._collection.count() == 0:
            return []

        return await asyncio.to_thread(
            self._retrieve_sync,
            query,
            subject,
            knowledge_context,
            max(3, min(top_k, 5)),
        )

    def _retrieve_sync(
        self,
        query: str,
        subject: str,
        knowledge_context: str | None,
        top_k: int,
    ) -> list[RAGChunk]:
        """执行 ChromaDB 查询，并对上下文命中的片段加权。"""
        assert self._collection is not None
        general_chunks = self._query_collection(
            query=query,
            count=min(top_k * 2, self._collection.count()),
            where={"subject": subject},
        )
        context_chunks: list[RAGChunk] = []
        if knowledge_context:
            context_chunks = self._query_collection(
                query=query,
                count=top_k,
                where={
                    "$and": [
                        {"subject": subject},
                        {"knowledge_point_id": knowledge_context},
                    ]
                },
            )

        chunks_by_id: dict[str, RAGChunk] = {}
        for chunk in [*context_chunks, *general_chunks]:
            score = chunk.score
            if (
                knowledge_context
                and chunk.metadata.get("knowledge_point_id")
                == knowledge_context
            ):
                score = min(1.0, score + 0.15)
            previous = chunks_by_id.get(chunk.id)
            if previous is None or score > previous.score:
                chunks_by_id[chunk.id] = RAGChunk(
                    id=chunk.id,
                    document=chunk.document,
                    metadata=chunk.metadata,
                    score=score,
                )

        return sorted(
            chunks_by_id.values(),
            key=lambda chunk: (-chunk.score, chunk.id),
        )[:top_k]

    def _query_collection(
        self,
        *,
        query: str,
        count: int,
        where: dict[str, object] | None = None,
    ) -> list[RAGChunk]:
        """查询一次 Chroma 集合并转换结果。"""
        assert self._collection is not None
        result = self._collection.query(
            query_texts=[query],
            n_results=max(1, count),
            where=where,
            include=["documents", "metadatas", "distances"],
        )
        ids = result.get("ids", [[]])[0]
        documents = result.get("documents", [[]])[0]
        metadatas = result.get("metadatas", [[]])[0]
        distances = result.get("distances", [[]])[0]

        chunks: list[RAGChunk] = []
        for index, chunk_id in enumerate(ids):
            metadata = {
                str(key): str(value)
                for key, value in (metadatas[index] or {}).items()
            }
            distance = float(distances[index])
            chunks.append(
                RAGChunk(
                    id=chunk_id,
                    document=documents[index] or "",
                    metadata=metadata,
                    score=max(0.0, min(1.0, 1.0 - distance)),
                )
            )
        return chunks


rag_service = RAGService()
