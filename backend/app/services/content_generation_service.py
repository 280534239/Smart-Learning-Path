"""模型驱动的可配置学习内容生成服务。"""

import asyncio
import json
import logging
import re
import time
from hashlib import blake2b
from pathlib import Path
from typing import Any, Literal
from urllib.parse import quote_plus

from pydantic import BaseModel, Field, ValidationError

from app.core.llm import LLMServiceError, llm_service
from app.schemas.knowledge import (
    GenerateSubjectRequest,
    DetailedLearningResource,
    KnowledgeEdge,
    KnowledgeGraphData,
    KnowledgeGraphDocument,
    KnowledgePointDetail,
    KnowledgePointNode,
    LearningResource,
)
from app.services.knowledge_service import (
    GENERATED_GRAPH_DIR,
    KnowledgeGraphError,
    knowledge_service,
)
from app.services.goal_priority_service import (
    format_goal_text,
    normalize_goal_priorities,
)

logger = logging.getLogger(__name__)


class ContentGenerationError(Exception):
    """学习内容无法生成。"""


class ContentGenerationUnavailableError(ContentGenerationError):
    """当前环境未配置可用的内容生成模型。"""


class _OutlineNode(BaseModel):
    """模型生成的临时大纲节点。"""

    id: str = Field(min_length=1, max_length=80)
    name: str = Field(min_length=1, max_length=100)
    description: str = Field(min_length=1, max_length=800)
    category: str = Field(min_length=1, max_length=50)
    difficulty: int = Field(ge=1, le=5)
    prerequisites: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)


class _OutlinePayload(BaseModel):
    """模型返回的完整学习大纲。"""

    description: str = Field(default="", max_length=1000)
    nodes: list[_OutlineNode]


class _GeneratedQuestion(BaseModel):
    """模型返回的单道练习题。"""

    type: Literal["choice", "fill_blank", "short_answer"]
    difficulty: int = Field(ge=1, le=5)
    question: str = Field(min_length=1, max_length=1000)
    options: list[str] = Field(default_factory=list)
    answer: str = Field(min_length=1, max_length=500)
    accepted_answers: list[str] = Field(default_factory=list)
    explanation: str = Field(min_length=1, max_length=1200)


class _QuestionSetPayload(BaseModel):
    """模型返回的练习题集合。"""

    questions: list[_GeneratedQuestion]


class _ResourceDraft(BaseModel):
    """模型生成的单份详细学习资源。"""

    type: Literal["article", "tutorial", "reference", "video"]
    title: str = Field(min_length=1, max_length=120)
    content: str = Field(min_length=200, max_length=12000)


class _ResourceSetPayload(BaseModel):
    """模型生成的学习资源集合。"""

    resources: list[_ResourceDraft]


class ContentGenerationService:
    """把用户主题转换为可校验的图谱和练习题。"""

    async def generate_subject(
        self,
        request: GenerateSubjectRequest,
        *,
        owner_user_id: int,
    ) -> KnowledgeGraphData:
        """生成、校验并持久化一份新的学习内容图谱。"""
        if not llm_service.is_configured:
            raise ContentGenerationUnavailableError(
                "生成自定义学习内容需要先配置 AI_API_KEY"
            )

        topic = request.topic.strip()
        subject_key = self._subject_key(topic, owner_user_id)
        prompt = self._build_outline_prompt(request, topic)
        last_error = ""
        last_exception: Exception | None = None
        started_at = time.perf_counter()

        for attempt in range(2):
            system_prompt = (
                "你是一位严谨的课程设计专家。只输出合法 JSON，"
                "不要输出 Markdown、解释或代码围栏。"
            )
            user_prompt = prompt
            if last_error:
                user_prompt = (
                    f"{prompt}\n\n上一次输出未通过校验：{last_error}。"
                    "请修正格式和依赖关系后重新输出完整 JSON。"
                )
            try:
                raw_reply = await llm_service.generate_reply(
                    system_prompt=system_prompt,
                    messages=[{"role": "user", "content": user_prompt}],
                    temperature=0.2,
                    max_tokens=3600,
                    response_format={"type": "json_object"},
                )
                payload = _OutlinePayload.model_validate(
                    self._extract_json(raw_reply)
                )
                document = self._build_graph_document(
                    request=request,
                    topic=topic,
                    subject_key=subject_key,
                    payload=payload,
                )
            except LLMServiceError as exc:
                last_exception = exc
                last_error = str(exc)[:300]
                logger.warning(
                    "学习内容模型调用失败 attempt=%d error=%s",
                    attempt + 1,
                    last_error,
                )
                if attempt == 0 and exc.retryable:
                    await asyncio.sleep(1)
                continue
            except (
                ContentGenerationError,
                KnowledgeGraphError,
                ValidationError,
                ValueError,
                KeyError,
                json.JSONDecodeError,
            ) as exc:
                last_exception = exc
                last_error = str(exc)[:300]
                logger.warning(
                    "学习内容生成校验失败 attempt=%d error=%s",
                    attempt + 1,
                    last_error,
                )
                continue

            await self._save_graph(subject_key, document)
            logger.info(
                "生成学习内容成功 subject=%s nodes=%d elapsed=%.2fs",
                subject_key,
                len(document.nodes),
                time.perf_counter() - started_at,
            )
            return await knowledge_service.get_graph(subject_key)

        if isinstance(last_exception, LLMServiceError):
            raise ContentGenerationError(str(last_exception))
        raise ContentGenerationError(
            "模型生成的学习大纲未通过校验，请调整主题描述后重试"
        )

    async def generate_questions(
        self,
        *,
        subject: str,
        point: KnowledgePointDetail,
        difficulty: int,
        count: int,
        learning_goal: str | None = None,
    ) -> list[dict[str, Any]]:
        """为指定知识点即时生成一组可自动批改的练习题。"""
        if not llm_service.is_configured:
            raise ContentGenerationUnavailableError(
                "生成练习题需要先配置 AI_API_KEY"
            )

        graph = await knowledge_service.get_graph(subject)
        prompt = self._build_question_prompt(
            graph_title=graph.title,
            point=point,
            difficulty=difficulty,
            count=count,
            learning_goal=learning_goal,
        )
        last_error = ""
        last_exception: Exception | None = None
        started_at = time.perf_counter()

        for attempt in range(2):
            system_prompt = (
                "你是一位考试命题专家。只输出合法 JSON，"
                "不要输出 Markdown、解释或代码围栏。"
            )
            user_prompt = prompt
            if last_error:
                user_prompt = (
                    f"{prompt}\n\n上一次输出未通过校验：{last_error}。"
                    "请修正后重新输出完整 JSON。"
                )
            try:
                raw_reply = await llm_service.generate_reply(
                    system_prompt=system_prompt,
                    messages=[{"role": "user", "content": user_prompt}],
                    temperature=0.3,
                    max_tokens=max(1200, min(2600, count * 420)),
                    response_format={"type": "json_object"},
                )
                payload = _QuestionSetPayload.model_validate(
                    self._extract_json(raw_reply)
                )
                questions = self._normalize_questions(
                    payload.questions,
                    difficulty=difficulty,
                    count=count,
                )
                if not questions:
                    raise ContentGenerationError("模型没有返回可用题目")
                logger.info(
                    "生成练习题成功 point=%s count=%d elapsed=%.2fs",
                    point.id,
                    len(questions),
                    time.perf_counter() - started_at,
                )
                return questions
            except LLMServiceError as exc:
                last_exception = exc
                last_error = str(exc)[:300]
                logger.warning(
                    "练习题模型调用失败 attempt=%d error=%s",
                    attempt + 1,
                    last_error,
                )
                if attempt == 0 and exc.retryable:
                    await asyncio.sleep(1)
                continue
            except (
                ContentGenerationError,
                ValidationError,
                ValueError,
                KeyError,
                json.JSONDecodeError,
            ) as exc:
                last_exception = exc
                last_error = str(exc)[:300]
                logger.warning(
                    "练习题生成校验失败 attempt=%d error=%s",
                    attempt + 1,
                    last_error,
                )
                continue

        if isinstance(last_exception, LLMServiceError):
            raise ContentGenerationError(str(last_exception))
        raise ContentGenerationError(
            "模型生成的练习题未通过校验，请稍后重试"
        )

    async def generate_learning_resources(
        self,
        *,
        point: KnowledgePointDetail,
    ) -> list[DetailedLearningResource]:
        """为知识点按需生成包含完整知识讲解的学习资源。"""
        subject = await knowledge_service.get_point_subject(point.id)
        graph = await knowledge_service.get_graph(subject)
        if not llm_service.is_configured:
            return self._fallback_learning_resources(
                point=point,
                graph_title=graph.title,
            )

        prompt = self._build_resource_prompt(
            graph_title=graph.title,
            point=point,
        )
        last_error = ""
        started_at = time.perf_counter()

        for attempt in range(2):
            system_prompt = (
                "你是一位学习资源策划师。只输出合法 JSON，"
                "不要输出 Markdown、解释或代码围栏。"
            )
            user_prompt = prompt
            if last_error:
                user_prompt = (
                    f"{prompt}\n\n上一次输出未通过校验：{last_error}。"
                    "请修正后重新输出完整 JSON。"
                )
            try:
                raw_reply = await llm_service.generate_reply(
                    system_prompt=system_prompt,
                    messages=[{"role": "user", "content": user_prompt}],
                    temperature=0.4,
                    max_tokens=8000,
                    response_format={"type": "json_object"},
                )
                payload = _ResourceSetPayload.model_validate(
                    self._extract_json(raw_reply)
                )
                resources = self._normalize_learning_resources(
                    payload.resources,
                    point=point,
                    graph_title=graph.title,
                )
                if not resources:
                    raise ContentGenerationError("模型没有返回可用学习资源")
                logger.info(
                    "生成学习资源成功 point=%s count=%d elapsed=%.2fs",
                    point.id,
                    len(resources),
                    time.perf_counter() - started_at,
                )
                return resources
            except (
                LLMServiceError,
                ContentGenerationError,
                ValidationError,
                ValueError,
                KeyError,
                json.JSONDecodeError,
            ) as exc:
                last_error = str(exc)[:300]
                logger.warning(
                    "学习资源生成失败 attempt=%d error=%s",
                    attempt + 1,
                    last_error,
                )

        return self._fallback_learning_resources(
            point=point,
            graph_title=graph.title,
        )

    @staticmethod
    def _subject_key(topic: str, owner_user_id: int) -> str:
        """按用户和主题生成稳定且互不冲突的内容标识。"""
        normalized = re.sub(r"\s+", " ", topic).strip().casefold()
        digest = blake2b(
            normalized.encode("utf-8"),
            digest_size=8,
        ).hexdigest()
        return f"custom_{owner_user_id}_{digest}"

    @staticmethod
    def _extract_json(raw_reply: str) -> dict[str, Any]:
        """从模型回复中提取首个完整 JSON 对象。"""
        cleaned = raw_reply.strip()
        fenced = re.search(
            r"```(?:json)?\s*(\{.*\})\s*```",
            cleaned,
            flags=re.DOTALL | re.IGNORECASE,
        )
        if fenced:
            cleaned = fenced.group(1)

        start = cleaned.find("{")
        end = cleaned.rfind("}")
        if start < 0 or end <= start:
            raise ValueError("模型回复中没有 JSON 对象")
        value = json.loads(cleaned[start:end + 1])
        if not isinstance(value, dict):
            raise ValueError("模型返回的 JSON 根节点必须是对象")
        return value

    @staticmethod
    def _build_outline_prompt(
        request: GenerateSubjectRequest,
        topic: str,
    ) -> str:
        """构造学习大纲生成提示词。"""
        priorities = normalize_goal_priorities(
            request.goal_priorities,
            request.goal,
        )
        priority_text = "\n".join(
            f"{index}. {item}"
            for index, item in enumerate(priorities, start=1)
        ) or "1. 建立系统、可实践的知识体系"
        return f"""
请为学习主题“{topic}”设计一份由浅入深的知识图谱大纲。

学习目标优先级（数字越小越重要）：
{priority_text}

学习者当前水平：{request.level}
知识点数量：请根据主题范围控制在 6 到 14 个之间，并保持内容紧凑完整，不要机械固定为某个数量。

输出 JSON，结构必须严格如下：
{{
  "description": "这份学习内容的简短说明",
  "nodes": [
    {{
      "id": "n1",
      "name": "知识点名称",
      "description": "面向学习者的具体解释，包含关键概念和学习要点，控制在 80-180 字",
      "category": "知识模块，3 到 5 个模块之一",
      "difficulty": 1,
      "prerequisites": [],
      "tags": ["标签1", "标签2"]
    }}
  ]
}}

要求：
1. 所有节点组成有向无环图，前置依赖只能引用已经出现的节点 id。
2. 至少包含一个无前置依赖的起点，并确保后续节点逐步递进。
3. id 使用 n1、n2 这样的短小写 ASCII 标识，不得重复。
4. difficulty 为 1-5 的整数，整体难度符合“{request.level}”水平。
5. category 控制在 3-5 个，名称简洁；节点名称和描述使用中文。
6. 内容要围绕主题本身，具体、准确、可用于学习，不要只写空泛的学习方法。
7. 知识点的覆盖和标签应优先服务第 1 优先级目标，再依次兼顾后续目标。
8. 节点划分应以完整覆盖主题且便于逐步学习为准，数量保持在 6 到 14 个。
9. 输出保持紧凑，不要重复解释，不要输出 resources、edges、节点数量等额外字段，只输出上述 JSON。
""".strip()

    @staticmethod
    def _build_question_prompt(
        *,
        graph_title: str,
        point: KnowledgePointDetail,
        difficulty: int,
        count: int,
        learning_goal: str | None = None,
    ) -> str:
        """构造知识点练习题生成提示词。"""
        tags = "、".join(point.tags) if point.tags else "无"
        goal_context = (
            f"\n学习目标：{learning_goal}"
            "\n命题时应优先检查该目标所需的关键概念和应用能力。"
            if learning_goal
            else ""
        )
        return f"""
请围绕“{graph_title}”中的知识点命制 {count} 道练习题。

知识点：{point.name}
模块：{point.category}
原始难度：{point.difficulty}
描述：{point.description}
标签：{tags}
本次目标难度：{difficulty}（1-5）
{goal_context}

输出 JSON，结构必须严格如下：
{{
  "questions": [
    {{
      "type": "choice",
      "difficulty": {difficulty},
      "question": "题干",
      "options": ["A. 选项一", "B. 选项二", "C. 选项三", "D. 选项四"],
      "answer": "A",
      "accepted_answers": [],
      "explanation": "解析"
    }}
  ]
}}

要求：
1. type 只能是 choice、fill_blank、short_answer。
2. 优先使用 choice，确保答案唯一且可以自动批改。
3. choice 必须有 4 个选项，每个选项以 A.、B.、C.、D. 开头，answer 只能是单个大写字母。
4. fill_blank 和 short_answer 的标准答案要简短明确，accepted_answers 提供可接受的等价写法。
5. explanation 必须解释原因，不能只重复答案。
6. 题目之间不能重复，不要输出 JSON 之外的任何文字。
""".strip()

    @staticmethod
    def _build_resource_prompt(
        *,
        graph_title: str,
        point: KnowledgePointDetail,
    ) -> str:
        """构造知识点详细学习资源生成提示词。"""
        tags = "、".join(point.tags) if point.tags else "无"
        return f"""
请为“{graph_title}”中的知识点“{point.name}”生成 6 份详细学习资源。

模块：{point.category}
难度：{point.difficulty}
描述：{point.description}
标签：{tags}

输出 JSON，结构必须严格如下：
{{
  "resources": [
    {{
      "type": "article",
      "title": "资源标题",
      "content": "使用 Markdown 编写的详细知识正文，必须包含小标题、完整解释、过程说明和具体例子"
    }}
  ]
}}

要求：
1. type 只能是 article、tutorial、reference、video。
2. 6 份资源分别深入讲解：核心定义与适用范围、关键原理与运行机制、
   分步示例拆解、条件变化与举一反三、常见误区与纠偏、练习与自检清单。
3. 每份 content 为 500-900 个中文字符，必须是可直接学习的完整正文，
   不能是摘要、导读、要点清单或学习建议。
4. content 使用 Markdown 二级标题划分知识层次，至少包含 3 个小节；
   根据主题使用“概念解释、成立条件、操作步骤、示例、结果分析、
   边界情况、常见错误、自检方法”等合适结构。
5. 内容必须具体解释“是什么、为什么、怎么做、何时会失效”，
   包含可验证的过程或例子，不能只重复知识点描述或堆砌套话。
6. 6 份资源各有独立学习切口，标题和正文不能互相重复。
7. 不要生成摘要、要点清单或 URL，也不要输出 JSON 之外的文字。
""".strip()

    @staticmethod
    def _build_graph_document(
        *,
        request: GenerateSubjectRequest,
        topic: str,
        subject_key: str,
        payload: _OutlinePayload,
    ) -> KnowledgeGraphDocument:
        """把模型大纲转换为通过 DAG 校验的正式图谱文档。"""
        if len(payload.nodes) < 6:
            raise ContentGenerationError("生成的知识点数量不足")

        outline_nodes = payload.nodes[:20]
        raw_ids = [node.id.strip() for node in outline_nodes]
        if len(set(raw_ids)) != len(raw_ids):
            raise ContentGenerationError("生成的节点 id 存在重复")

        id_map = {
            raw_id: f"{subject_key}_{index:02d}"
            for index, raw_id in enumerate(raw_ids, start=1)
        }
        nodes: list[KnowledgePointNode] = []
        edges: list[KnowledgeEdge] = []

        for index, outline in enumerate(outline_nodes, start=1):
            new_id = id_map[outline.id.strip()]
            prerequisites = []
            for raw_prerequisite in outline.prerequisites:
                prerequisite = id_map.get(raw_prerequisite.strip())
                if prerequisite is None:
                    raise ContentGenerationError(
                        f"节点 {outline.id} 引用了不存在的前置节点"
                    )
                if prerequisite == new_id:
                    raise ContentGenerationError("节点不能依赖自身")
                if prerequisite not in prerequisites:
                    prerequisites.append(prerequisite)

            tags = [
                tag.strip()[:30]
                for tag in outline.tags
                if tag and tag.strip()
            ][:6]
            search_query = quote_plus(f"{topic} {outline.name}")
            nodes.append(
                KnowledgePointNode(
                    id=new_id,
                    name=outline.name.strip(),
                    description=outline.description.strip(),
                    category=outline.category.strip(),
                    difficulty=max(1, min(5, outline.difficulty)),
                    prerequisites=prerequisites,
                    resources=[
                        LearningResource(
                            type="search",
                            title=f"检索：{outline.name}",
                            url=(
                                "https://www.bing.com/search?q="
                                f"{search_query}"
                            ),
                        )
                    ],
                    tags=tags,
                )
            )
            edges.extend(
                KnowledgeEdge(
                    source=prerequisite,
                    target=new_id,
                    relation="prerequisite",
                )
                for prerequisite in prerequisites
            )

        priorities = normalize_goal_priorities(
            request.goal_priorities,
            request.goal,
        )
        description = payload.description.strip() or (
            format_goal_text(priorities)
            if priorities
            else f"围绕“{topic}”生成的个性化学习内容"
        )
        document = KnowledgeGraphDocument(
            subject=topic,
            version="generated-1.0.0",
            description=description[:1000],
            node_count=len(nodes),
            edge_count=len(edges),
            nodes=nodes,
            edges=edges,
        )
        knowledge_service.validate_document(document)
        return document

    @classmethod
    async def _save_graph(
        cls,
        subject_key: str,
        document: KnowledgeGraphDocument,
    ) -> None:
        """原子写入图谱文件并刷新内存索引。"""
        GENERATED_GRAPH_DIR.mkdir(parents=True, exist_ok=True)
        path = GENERATED_GRAPH_DIR / f"{subject_key}.json"
        temporary_path = path.with_suffix(".json.tmp")
        raw_data = document.model_dump(mode="json")
        await cls._write_json(temporary_path, raw_data)
        temporary_path.replace(path)
        await knowledge_service.load_all(force=True)

    @staticmethod
    async def _write_json(path: Path, payload: dict[str, Any]) -> None:
        """将 JSON 内容写入指定文件。"""
        await asyncio.to_thread(
            path.write_text,
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    @staticmethod
    def _normalize_questions(
        questions: list[_GeneratedQuestion],
        *,
        difficulty: int,
        count: int,
    ) -> list[dict[str, Any]]:
        """规范化模型题目并过滤无法自动批改的结果。"""
        normalized: list[dict[str, Any]] = []
        for item in questions[: max(1, count)]:
            question = item.question.strip()
            answer = item.answer.strip()
            explanation = item.explanation.strip()
            if not question or not answer or not explanation:
                continue

            options = [option.strip() for option in item.options if option.strip()]
            if item.type == "choice":
                if len(options) < 2:
                    continue
                options = [
                    (
                        option
                        if re.match(
                            rf"^{chr(65 + index)}[.、\s]",
                            option,
                            flags=re.IGNORECASE,
                        )
                        else f"{chr(65 + index)}. {option}"
                    )
                    for index, option in enumerate(options[:4])
                ]
                letter = answer[:1].upper()
                if not (
                    "A" <= letter <= chr(64 + len(options))
                ):
                    continue
                answer = letter

            normalized.append(
                {
                    "type": item.type,
                    "difficulty": max(1, min(5, difficulty)),
                    "question": question,
                    "options": options[:4] if item.type == "choice" else [],
                    "answer": answer,
                    "accepted_answers": [
                        value.strip()
                        for value in item.accepted_answers
                        if value.strip()
                    ][:6],
                    "explanation": explanation,
                }
            )
        return normalized

    @staticmethod
    def _normalize_learning_resources(
        resources: list[_ResourceDraft],
        *,
        point: KnowledgePointDetail,
        graph_title: str,
    ) -> list[DetailedLearningResource]:
        """校验模型资源并补充稳定可用的检索链接。"""
        normalized: list[DetailedLearningResource] = []
        seen_titles: set[str] = set()
        for item in resources[:6]:
            title = item.title.strip()
            content = item.content.strip()
            if not title or len(content) < 200 or title in seen_titles:
                continue
            search_query = quote_plus(
                f"{graph_title} {point.name} {title}"
            )
            normalized.append(
                DetailedLearningResource(
                    type=item.type,
                    title=title,
                    url=(
                        "https://www.bing.com/search?q="
                        f"{search_query}"
                    ),
                    content=content,
                )
            )
            seen_titles.add(title)
        return normalized

    @staticmethod
    def _fallback_learning_resources(
        *,
        point: KnowledgePointDetail,
        graph_title: str,
    ) -> list[DetailedLearningResource]:
        """模型不可用时提供结构化、可完整学习的基础正文。"""
        drafts = [
            {
                "type": "article",
                "title": f"{point.name}：核心定义与适用范围",
                "content": (
                    f"## 核心定义\n{point.description}\n\n"
                    f"## 它解决什么问题\n"
                    f"{point.name} 的价值不是提供一个可以机械背诵的结论，"
                    "而是帮助学习者判断某类问题应当如何描述、分析和处理。"
                    "理解定义时应同时明确对象、目标以及判断结果是否正确的方法。\n\n"
                    "## 适用范围\n"
                    "检查使用前需要满足的条件，区分概念本身的定义与某个具体实现方式。"
                    "当输入、前提或目标发生变化时，先判断结论是否仍然成立，"
                    "再决定能否继续套用已有方法。"
                ),
            },
            {
                "type": "article",
                "title": f"{point.name}：关键原理与运行过程",
                "content": (
                    f"## 前提条件\n"
                    f"理解 {point.name} 时，先把问题拆成前提、过程和结果。"
                    "前提是方法能够成立的环境和输入约束；如果前提不满足，"
                    "即使操作步骤看起来相同，结果也可能失去意义。\n\n"
                    "## 运行过程\n"
                    "按照时间或逻辑顺序列出关键步骤，并记录每一步接收什么输入、"
                    "执行什么处理、产生什么中间结果。将中间结果与前一步连接起来，"
                    "可以判断某个结论是由哪条规则或因果关系产生的。\n\n"
                    "## 结果检查\n"
                    "最后检查输出是否满足目标，并解释结果为什么合理。"
                    "如果只记住最终结果，却无法说明条件和过程，"
                    "就难以把知识迁移到新的问题中。"
                ),
            },
            {
                "type": "tutorial",
                "title": f"{point.name}：最小示例分步拆解",
                "content": (
                    f"## 示例目标\n"
                    f"选择一个能够完整跟踪的最小案例来学习 {point.name}。"
                    "示例开始前先写明已知条件、初始状态和希望得到的结果，"
                    "不要一开始就引入过多变量。\n\n"
                    "## 分步执行\n"
                    "每一步只执行一个明确动作，并记录这一步使用了哪些信息、"
                    "产生了哪些变化。遇到判断时，写出判断依据而不是直接给出答案。"
                    "这样可以把最终结果与知识点中的规则逐项对应起来。\n\n"
                    "## 结果解释\n"
                    "完成后重新检查示例，说明每个中间结果为什么出现，"
                    "以及最终结果是否满足最初目标。若结果与预期不同，"
                    "从第一个出现差异的步骤开始定位，而不是只修改最终答案。"
                ),
            },
            {
                "type": "tutorial",
                "title": f"{point.name}：条件变化与举一反三",
                "content": (
                    f"## 单一变量变化\n"
                    f"掌握基本示例后，每次只改变 {point.name} 的一个条件，"
                    "例如输入内容、数量、顺序或边界值。变化前先根据原理预测结果，"
                    "执行后再比较预测与实际结果。\n\n"
                    "## 区分影响层次\n"
                    "有些变化只改变结果数值，有些变化会改变处理步骤，"
                    "还有一些变化会直接破坏使用前提。学习时要能指出变化属于哪一类，"
                    "并说明判断依据。\n\n"
                    "## 形成迁移规律\n"
                    "把多次变化中稳定出现的规律记录下来，同时记录首次失效的条件。"
                    "稳定的规律说明适用范围，失效条件则划出知识边界，"
                    "二者共同构成可以迁移到新问题中的理解。"
                ),
            },
            {
                "type": "reference",
                "title": f"{point.name}：常见误区与纠偏",
                "content": (
                    f"## 常见错误类型\n"
                    f"学习 {point.name} 时，常见问题包括只记结论而说不清前提、"
                    "混淆定义与具体实现、忽略边界条件，以及只会照搬示例。"
                    "这些错误的共同点是缺少对条件和过程的解释。\n\n"
                    "## 定位错误\n"
                    "不要只说“答案错了”，而要指出错误首次出现的环节："
                    "是前提判断错误、信息读取错误、步骤顺序错误，还是结果检查遗漏。"
                    "定位到具体环节后，才能选择正确的修正方法。\n\n"
                    "## 用反例纠偏\n"
                    "构造一个不满足条件或结论相反的案例，观察方法是否失效，"
                    "并解释失效原因。能够正确说明反例，通常比再做一道相似题"
                    "更能证明已经理解知识边界。"
                ),
            },
            {
                "type": "reference",
                "title": f"{point.name}：练习与自检清单",
                "content": (
                    f"## 知识复述\n"
                    f"合上资料后，用自己的话解释 {point.name} 的定义、作用、"
                    "前提条件和一个具体例子。复述时不照抄原文，"
                    "重点检查这些内容之间是否形成完整逻辑。\n\n"
                    "## 独立练习\n"
                    "先完成一个最小示例，再完成一个改变条件后的变式题。"
                    "答题过程中写出关键判断依据，结果出来后检查错误发生在哪一步。"
                    "如果卡住，只回到对应知识环节，而不是重新浏览全部内容。\n\n"
                    "## 自检标准\n"
                    "能够说明是什么、为什么这样做、怎样判断结果正确，"
                    "并能指出一个不适用的情况，才算形成较完整的理解。"
                    "最后记录仍未解决的问题，作为下一次学习的起点。"
                ),
            },
        ]
        resources: list[DetailedLearningResource] = []
        for draft in drafts:
            search_query = quote_plus(
                f"{graph_title} {point.name} {draft['title']}"
            )
            resources.append(
                DetailedLearningResource(
                    type=draft["type"],
                    title=draft["title"],
                    url=f"https://www.bing.com/search?q={search_query}",
                    content=draft["content"],
                )
            )
        return resources


content_generation_service = ContentGenerationService()

__all__ = [
    "ContentGenerationError",
    "ContentGenerationService",
    "ContentGenerationUnavailableError",
    "content_generation_service",
]
