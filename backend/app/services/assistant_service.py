"""悬浮 AI 小助手的流式答疑逻辑。"""

import asyncio
import logging
from collections.abc import AsyncIterator
from dataclasses import dataclass

from app.core.llm import (
    LLMServiceError,
    assistant_llm_service,
)
from app.schemas.assistant import AssistantAskRequest
from app.services.knowledge_service import (
    KnowledgePointNotFoundError,
    knowledge_service,
)
from app.services.rag_service import RAGChunk, rag_service

logger = logging.getLogger(__name__)

ASSISTANT_SYSTEM_PROMPT = """你是“智学小助手”，一位耐心、准确、反应迅速的学习助手。

回答原则：
1. 先直接回答结论，再补充必要的原理、步骤或示例
2. 优先依据提供的检索资料，资料不足时明确说明，不编造事实
3. 使用简体中文和 Markdown，内容简洁，适合学生快速阅读
4. 代码使用带语言标记的 Markdown 代码块
5. 回答必须一次给出完整答案，不要用反问代替解答
"""


@dataclass(slots=True)
class AssistantPreparation:
    """完成检索后、开始生成前的助手上下文。"""

    subject: str
    content_title: str
    chunks: list[RAGChunk]
    related_knowledge: list[str]


class AssistantService:
    """协调 RAG 检索、独立模型和流式回答。"""

    async def prepare(
        self,
        payload: AssistantAskRequest,
    ) -> AssistantPreparation:
        """读取当前学习内容并检索与问题相关的资料。"""
        graph = await knowledge_service.get_graph(payload.subject)
        knowledge_context = payload.knowledge_context
        if knowledge_context:
            try:
                context_subject = (
                    await knowledge_service.get_point_subject(
                        knowledge_context
                    )
                )
            except KnowledgePointNotFoundError:
                knowledge_context = None
            else:
                if context_subject != graph.subject:
                    knowledge_context = None

        chunks = await rag_service.retrieve(
            payload.message,
            subject=graph.subject,
            knowledge_context=knowledge_context,
            top_k=3,
        )
        related: list[str] = []
        for chunk in chunks:
            point_id = chunk.metadata.get("knowledge_point_id")
            if point_id and point_id not in related:
                related.append(point_id)
        if knowledge_context and knowledge_context not in related:
            related.insert(0, knowledge_context)

        return AssistantPreparation(
            subject=graph.subject,
            content_title=graph.title,
            chunks=chunks,
            related_knowledge=related,
        )

    async def stream_ask(
        self,
        payload: AssistantAskRequest,
        preparation: AssistantPreparation,
    ) -> AsyncIterator[dict[str, object]]:
        """按 SSE 事件结构生成模型回答。"""
        if not assistant_llm_service.is_configured:
            async for event in self._stream_mock_reply(
                payload.message,
                preparation,
            ):
                yield event
            return

        model_name = assistant_llm_service.model_name
        yield {"type": "meta", "model": model_name}
        system_prompt = self._build_system_prompt(
            preparation,
            page_title=payload.page_title,
        )
        messages = [
            {"role": turn.role, "content": turn.content}
            for turn in payload.history[-8:]
        ]
        messages.append({"role": "user", "content": payload.message})

        yielded_content = False
        try:
            async for content in assistant_llm_service.stream_reply(
                system_prompt=system_prompt,
                messages=messages,
                temperature=0.55,
                max_tokens=1000,
            ):
                yielded_content = True
                yield {"type": "delta", "content": content}
        except LLMServiceError:
            logger.exception("悬浮助手模型调用失败")
            yield {
                "type": "error",
                "message": "回答暂时中断，请稍后重试",
            }
            return

        if not yielded_content:
            yield {
                "type": "error",
                "message": "模型没有返回内容，请重新提问",
            }
            return
        yield {
            "type": "done",
            "related_knowledge": preparation.related_knowledge,
        }

    async def _stream_mock_reply(
        self,
        message: str,
        preparation: AssistantPreparation,
    ) -> AsyncIterator[dict[str, object]]:
        """未配置模型时仍提供可读的即时回答。"""
        yield {"type": "meta", "model": "local-preview"}
        reply = self._mock_reply(message, preparation)
        for index in range(0, len(reply), 4):
            yield {"type": "delta", "content": reply[index : index + 4]}
            await asyncio.sleep(0.01)
        yield {
            "type": "done",
            "related_knowledge": preparation.related_knowledge,
        }

    @staticmethod
    def _build_system_prompt(
        preparation: AssistantPreparation,
        *,
        page_title: str | None,
    ) -> str:
        """拼接学习内容、页面上下文和 RAG 资料。"""
        page = page_title or "学习页面"
        lines = [
            f"当前学习内容：{preparation.content_title}",
            f"学生所在页面：{page}",
            "",
            ASSISTANT_SYSTEM_PROMPT,
        ]
        if preparation.chunks:
            lines.append("\n以下是检索到的相关资料：")
            for index, chunk in enumerate(preparation.chunks, start=1):
                title = chunk.metadata.get("title", "知识片段")
                lines.append(
                    f"[{index}] {title}\n{chunk.document[:1000]}"
                )
        return "\n".join(lines)

    @staticmethod
    def _mock_reply(
        message: str,
        preparation: AssistantPreparation,
    ) -> str:
        """生成不依赖外部服务的本地预览回答。"""
        normalized = message.casefold()
        if "for" in normalized and "while" in normalized:
            return (
                "`for` 适合次数明确或遍历序列，`while` 适合由条件决定"
                "是否继续。\n\n"
                "```python\n"
                "for i in range(3):\n"
                "    print(i)\n\n"
                "count = 0\n"
                "while count < 3:\n"
                "    print(count)\n"
                "    count += 1\n"
                "```"
            )

        knowledge_chunk = next(
            (
                chunk
                for chunk in preparation.chunks
                if chunk.metadata.get("source_type") == "knowledge"
            ),
            None,
        )
        title = (
            knowledge_chunk.metadata.get("title")
            if knowledge_chunk
            else preparation.content_title
        )
        return (
            f"关于“{title}”，可以先把问题拆成三步：明确目标和输入，"
            "找出关键规则，再用一个小例子验证结果。\n\n"
            "如果你把具体题目或代码发出来，我可以直接给出下一步。"
        )


assistant_service = AssistantService()
