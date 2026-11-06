"""OpenAI 兼容接口的大模型调用封装。"""

import logging
from collections.abc import AsyncIterator
from typing import NoReturn

import httpx
from openai import AsyncOpenAI
from openai import (
    APIConnectionError,
    APIStatusError,
    APITimeoutError,
    InternalServerError,
    RateLimitError,
)

from app.core.config import get_settings

settings = get_settings()
logger = logging.getLogger(__name__)


class LLMServiceError(Exception):
    """大模型调用失败，并标记是否适合立即重试。"""

    def __init__(self, message: str, *, retryable: bool = False) -> None:
        super().__init__(message)
        self.retryable = retryable


class LLMService:
    """通过 OpenAI SDK 调用兼容 Chat Completions 的服务。"""

    def __init__(
        self,
        *,
        api_key: str | None = None,
        base_url: str | None = None,
        model_name: str | None = None,
    ) -> None:
        self._api_key = (
            settings.ai_api_key if api_key is None else api_key
        ).strip()
        self._base_url = (
            settings.ai_base_url if base_url is None else base_url
        ).strip()
        self._model_name = (
            settings.ai_model_name
            if model_name is None
            else model_name
        ).strip()
        self._client: AsyncOpenAI | None = None

    @property
    def is_configured(self) -> bool:
        """是否已配置 API Key。"""
        key = self._api_key
        return bool(
            key
            and key
            not in {
                "your-deepseek-api-key",
                "your-api-key",
            }
        )

    def _get_client(self) -> AsyncOpenAI:
        """延迟创建异步 OpenAI 客户端。"""
        if not self.is_configured:
            raise LLMServiceError("未配置 AI_API_KEY")
        if self._client is None:
            self._client = AsyncOpenAI(
                api_key=self._api_key,
                base_url=self._base_url,
                timeout=httpx.Timeout(
                    settings.ai_request_timeout_seconds,
                    connect=settings.ai_connect_timeout_seconds,
                ),
                max_retries=0,
            )
        return self._client

    async def generate_reply(
        self,
        *,
        system_prompt: str,
        messages: list[dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int = 700,
        response_format: dict[str, str] | None = None,
    ) -> str:
        """调用兼容 Chat Completions 的模型接口。"""
        client = self._get_client()
        request_options: dict[str, object] = {}
        if response_format is not None:
            request_options["response_format"] = response_format
        try:
            response = await client.chat.completions.create(
                model=self._model_name,
                messages=[
                    {"role": "system", "content": system_prompt},
                    *messages,
                ],
                temperature=temperature,
                max_tokens=max_tokens,
                **request_options,
            )
        except Exception as exc:
            self._raise_service_error(exc)

        if not response.choices:
            raise LLMServiceError("大模型未返回候选回答")
        choice = response.choices[0]
        content = choice.message.content
        if not content or not content.strip():
            if choice.finish_reason == "length":
                raise LLMServiceError(
                    "模型输出达到长度上限，请减小生成规模后重试",
                    retryable=True,
                )
            if getattr(choice.message, "reasoning_content", None):
                raise LLMServiceError(
                    "模型只返回了推理内容，请将 AI_MODEL_NAME "
                    "设置为 deepseek-chat"
                )
            raise LLMServiceError("大模型返回了空内容")
        return content.strip()

    async def stream_reply(
        self,
        *,
        system_prompt: str,
        messages: list[dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int = 900,
    ) -> AsyncIterator[str]:
        """流式调用兼容 Chat Completions 的模型接口。"""
        client = self._get_client()
        try:
            stream = await client.chat.completions.create(
                model=self._model_name,
                messages=[
                    {"role": "system", "content": system_prompt},
                    *messages,
                ],
                temperature=temperature,
                max_tokens=max_tokens,
                stream=True,
            )
            async for chunk in stream:
                if not chunk.choices:
                    continue
                content = chunk.choices[0].delta.content
                if content:
                    yield content
        except Exception as exc:
            self._raise_service_error(exc)

    def _raise_service_error(self, exc: Exception) -> NoReturn:
        """把 SDK 异常转换为可展示且可判断重试的错误。"""
        logger.warning(
            "模型调用失败 model=%s error_type=%s error=%s",
            self._model_name,
            type(exc).__name__,
            str(exc)[:500],
        )
        if isinstance(exc, APITimeoutError):
            raise LLMServiceError(
                (
                    "模型响应超时"
                    f"（{settings.ai_request_timeout_seconds:.0f} 秒），"
                    "请稍后重试"
                ),
                retryable=True,
            ) from exc
        if isinstance(exc, APIConnectionError):
            raise LLMServiceError(
                "无法连接模型服务，请检查网络或 AI_BASE_URL",
                retryable=True,
            ) from exc
        if isinstance(exc, RateLimitError):
            raise LLMServiceError(
                "模型服务请求过于频繁，请稍后重试",
                retryable=True,
            ) from exc
        if isinstance(exc, InternalServerError):
            raise LLMServiceError(
                "模型服务暂时不可用，请稍后重试",
                retryable=True,
            ) from exc
        if isinstance(exc, APIStatusError):
            status_code = exc.status_code
            if status_code in {401, 403}:
                message = "模型 API Key 无效或无访问权限"
            elif status_code == 404:
                message = (
                    f"模型名称不可用：{self._model_name}，"
                    "请检查 AI_MODEL_NAME 配置"
                )
            elif status_code == 429:
                message = "模型服务请求过于频繁，请稍后重试"
            elif status_code >= 500:
                message = "模型服务暂时不可用，请稍后重试"
            elif status_code == 400:
                message = (
                    f"模型请求参数无效：{self._model_name}，"
                    "请检查 AI_MODEL_NAME 配置"
                )
            else:
                message = f"模型调用失败（HTTP {status_code}）"
            raise LLMServiceError(
                message,
                retryable=status_code == 429 or status_code >= 500,
            ) from exc
        raise LLMServiceError("大模型服务暂时不可用") from exc

    @property
    def model_name(self) -> str:
        """返回当前服务使用的模型名称。"""
        return self._model_name

    async def close(self) -> None:
        """关闭底层 HTTP 客户端。"""
        if self._client is not None:
            await self._client.close()
            self._client = None


llm_service = LLMService()
chat_llm_service = LLMService(
    base_url=settings.ai_chat_base_url,
    model_name=settings.ai_chat_model_name,
)
assistant_llm_service = LLMService(
    api_key=settings.ai_assistant_api_key or settings.ai_api_key,
    base_url=settings.ai_assistant_base_url,
    model_name=settings.ai_assistant_model_name,
)
