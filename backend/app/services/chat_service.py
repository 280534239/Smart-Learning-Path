"""AI 答疑业务逻辑。"""

import logging
from datetime import UTC, datetime

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.llm import LLMServiceError, chat_llm_service
from app.models.chat_session import ChatSession
from app.models.user import User
from app.schemas.chat import (
    ChatAskData,
    ChatAskRequest,
    ChatDeleteData,
    ChatHistoryData,
    ChatMessage,
)
from app.services.rag_service import RAGChunk, rag_service
from app.services.knowledge_service import (
    KnowledgePointNotFoundError,
    knowledge_service,
)

logger = logging.getLogger(__name__)

ASSISTANT_SYSTEM_PROMPT = """你是一位耐心、准确的 AI 学习助手，名叫“智学小助手”。

回答原则：
1. 直接回答学生的问题，先给出清晰结论
2. 根据问题需要补充原理、关键步骤、示例或可运行代码
3. 优先依据检索资料回答；资料不足时明确说明，不要编造
4. 使用简体中文和 Markdown，表达简洁、准确、适合学生理解
5. 直接给出答案，除非学生明确要求练习，否则不要用问题代替答案
"""


class ChatNotFoundError(Exception):
    """会话或用户不存在。"""


class ChatService:
    """协调 RAG 检索、大模型与对话历史。"""

    async def ask(
        self,
        user_id: int,
        payload: ChatAskRequest,
        session: AsyncSession,
    ) -> ChatAskData:
        """检索知识片段并生成一次直接回答。"""
        if await session.get(User, user_id) is None:
            raise ChatNotFoundError(f"用户不存在: {user_id}")

        graph = await knowledge_service.get_graph(payload.subject)
        subject = graph.subject
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
                if context_subject != subject:
                    knowledge_context = None
        chunks = await rag_service.retrieve(
            payload.message,
            subject=subject,
            knowledge_context=knowledge_context,
            top_k=4,
        )
        related_knowledge = self._related_knowledge(
            chunks,
            knowledge_context,
        )
        chat_session = await self._get_session(
            user_id,
            payload.session_id,
            session,
        )
        messages = (
            list(chat_session.messages)
            if chat_session is not None
            else []
        )
        now = datetime.now(UTC).isoformat()
        messages.append(
            {
                "role": "user",
                "content": payload.message,
                "timestamp": now,
            }
        )

        system_prompt = self._build_system_prompt(
            chunks,
            content_title=graph.title,
        )
        llm_messages = self._recent_llm_messages(messages)
        if chat_llm_service.is_configured:
            try:
                reply = await chat_llm_service.generate_reply(
                    system_prompt=system_prompt,
                    messages=llm_messages,
                )
            except LLMServiceError:
                logger.exception("大模型调用失败，使用模拟回答")
                reply = self._mock_reply(payload.message, chunks)
        else:
            reply = self._mock_reply(payload.message, chunks)

        messages.append(
            {
                "role": "assistant",
                "content": reply,
                "timestamp": datetime.now(UTC).isoformat(),
            }
        )
        if chat_session is None:
            chat_session = ChatSession(
                user_id=user_id,
                subject=subject,
                session_id=payload.session_id,
                messages=messages,
                knowledge_context=knowledge_context,
            )
            session.add(chat_session)
        else:
            chat_session.subject = subject
            chat_session.messages = messages
            chat_session.knowledge_context = knowledge_context

        await session.commit()
        return ChatAskData(
            reply=reply,
            subject=subject,
            session_id=payload.session_id,
            related_knowledge=related_knowledge,
        )

    async def get_history(
        self,
        user_id: int,
        session_id: str,
        session: AsyncSession,
    ) -> ChatHistoryData:
        """根据会话 ID 返回历史消息。"""
        chat_session = await session.scalar(
            select(ChatSession)
            .where(
                ChatSession.user_id == user_id,
                ChatSession.session_id == session_id,
            )
            .order_by(ChatSession.created_at.desc())
            .limit(1)
        )
        if chat_session is None:
            raise ChatNotFoundError(f"会话不存在: {session_id}")

        messages = [
            ChatMessage.model_validate(message)
            for message in chat_session.messages
        ]
        return ChatHistoryData(
            subject=chat_session.subject,
            session_id=chat_session.session_id,
            messages=messages,
            knowledge_context=chat_session.knowledge_context,
            created_at=chat_session.created_at,
        )

    async def delete_history(
        self,
        user_id: int,
        session_id: str,
        session: AsyncSession,
    ) -> ChatDeleteData:
        """删除当前用户指定会话的全部历史。"""
        result = await session.execute(
            delete(ChatSession).where(
                ChatSession.user_id == user_id,
                ChatSession.session_id == session_id,
            )
        )
        await session.commit()
        return ChatDeleteData(
            session_id=session_id,
            deleted=bool(result.rowcount),
        )

    @staticmethod
    async def _get_session(
        user_id: int,
        session_id: str,
        session: AsyncSession,
    ) -> ChatSession | None:
        """查找用户已有的对话会话。"""
        return await session.scalar(
            select(ChatSession)
            .where(
                ChatSession.user_id == user_id,
                ChatSession.session_id == session_id,
            )
            .order_by(ChatSession.created_at.desc())
            .limit(1)
        )

    @staticmethod
    def _related_knowledge(
        chunks: list[RAGChunk],
        knowledge_context: str | None,
    ) -> list[str]:
        """从检索结果汇总去重后的相关知识点。"""
        related: list[str] = []
        for chunk in chunks:
            point_id = chunk.metadata.get("knowledge_point_id")
            if point_id and point_id not in related:
                related.append(point_id)
        if knowledge_context and knowledge_context not in related:
            related.insert(0, knowledge_context)
        return related

    @staticmethod
    def _build_system_prompt(
        chunks: list[RAGChunk],
        *,
        content_title: str,
    ) -> str:
        """将检索片段拼接到直接回答系统提示词。"""
        subject_context = f"当前学习内容：{content_title}\n\n"
        if not chunks:
            return f"{subject_context}{ASSISTANT_SYSTEM_PROMPT}"

        context_lines = []
        for index, chunk in enumerate(chunks, start=1):
            title = chunk.metadata.get("title", "知识片段")
            context_lines.append(
                f"[{index}] {title}\n{chunk.document[:1200]}"
            )
        context = "\n\n".join(context_lines)
        return (
            f"{subject_context}{ASSISTANT_SYSTEM_PROMPT}\n\n"
            f"以下是与学生问题最相关的检索资料：\n{context}\n\n"
            "请优先依据这些资料直接回答问题，并说明关键依据。"
        )

    @staticmethod
    def _recent_llm_messages(
        messages: list[dict[str, object]],
    ) -> list[dict[str, str]]:
        """截取最近对话并转换为 OpenAI 消息格式。"""
        result: list[dict[str, str]] = []
        for message in messages[-10:]:
            role = str(message.get("role", ""))
            content = str(message.get("content", ""))
            if role in {"user", "assistant"} and content:
                result.append({"role": role, "content": content})
        return result

    @staticmethod
    def _mock_reply(
        message: str,
        chunks: list[RAGChunk],
    ) -> str:
        """在未配置 API Key 时生成直接回答的模拟回复。"""
        normalized = message.casefold()
        if "for" in normalized and "while" in normalized:
            return (
                "`for` 和 `while` 都用于循环，主要区别是：\n\n"
                "- `for` 适合遍历已知序列，或循环次数已经确定的场景。\n"
                "- `while` 适合条件满足时持续执行，循环次数通常不确定。\n\n"
                "例如：\n\n"
                "```python\n"
                "for i in range(5):\n"
                "    print(i)\n\n"
                "count = 0\n"
                "while count < 5:\n"
                "    print(count)\n"
                "    count += 1\n"
                "```\n\n"
                "简单来说：次数明确优先用 `for`，依赖条件决定是否继续时用 `while`。"
            )

        knowledge_chunk = next(
            (
                chunk
                for chunk in chunks
                if chunk.metadata.get("source_type") == "knowledge"
            ),
            None,
        )
        if knowledge_chunk is not None:
            title = knowledge_chunk.metadata.get("title", "这个知识点")
            hint = knowledge_chunk.document.split("描述：", 1)[-1].split(
                "\n",
                1,
            )[0][:100]
        elif chunks:
            title = chunks[0].metadata.get("title", "这个问题")
            hint = "先找出题目中已经确定的条件，再观察结果如何一步步变化"
        else:
            title = "这个问题"
            hint = "先找出题目中已经确定的条件，再观察结果是如何一步步变化的"
        hint = hint.rstrip("。！？!? ")

        return (
            f"关于“{title}”，核心内容是：{hint}。\n\n"
            "解决具体问题时，可以先明确输入和条件，再按上述规则逐步推导。"
            "如果涉及代码，建议先写出最小示例，检查每一步的输入和输出。"
        )


chat_service = ChatService()
