"""
ml/llm/llm_router.py
--------------------
Multi-provider LLM abstraction layer with automatic failover and cost tracking.

Supported providers:
- OpenAI GPT-4o / GPT-3.5-turbo
- DeepSeek Chat API
- Ollama (local Llama 3 / Qwen / Mistral)

Features:
- Provider selection based on cost, speed, and availability
- Async streaming response via async generator
- Exponential-backoff retry on transient failures
- Token counting and per-request cost tracking
- Context window management with automatic truncation
- System prompt injection and role management
- Tool / function calling support (OpenAI-compatible)
- Conversation history management
"""

from __future__ import annotations

import asyncio
import json
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, AsyncIterator

import structlog

logger = structlog.get_logger(__name__)


# ──────────────────────────────────────────────────────────────────────────────
# Provider registry
# ──────────────────────────────────────────────────────────────────────────────


class LLMProvider(str, Enum):
    OPENAI = "openai"
    DEEPSEEK = "deepseek"
    OLLAMA = "ollama"
    AUTO = "auto"


@dataclass
class ProviderConfig:
    name: LLMProvider
    model: str
    max_context_tokens: int
    cost_per_1k_input: float    # USD
    cost_per_1k_output: float   # USD
    avg_tokens_per_second: float
    available: bool = True


PROVIDER_CONFIGS: dict[LLMProvider, ProviderConfig] = {
    LLMProvider.OPENAI: ProviderConfig(
        name=LLMProvider.OPENAI,
        model="gpt-4o",
        max_context_tokens=128_000,
        cost_per_1k_input=0.005,
        cost_per_1k_output=0.015,
        avg_tokens_per_second=80.0,
    ),
    LLMProvider.DEEPSEEK: ProviderConfig(
        name=LLMProvider.DEEPSEEK,
        model="deepseek-chat",
        max_context_tokens=64_000,
        cost_per_1k_input=0.0002,
        cost_per_1k_output=0.0002,
        avg_tokens_per_second=120.0,
    ),
    LLMProvider.OLLAMA: ProviderConfig(
        name=LLMProvider.OLLAMA,
        model="llama3.1:8b",
        max_context_tokens=8_192,
        cost_per_1k_input=0.0,
        cost_per_1k_output=0.0,
        avg_tokens_per_second=20.0,
    ),
}


# ──────────────────────────────────────────────────────────────────────────────
# Data containers
# ──────────────────────────────────────────────────────────────────────────────


@dataclass
class Message:
    role: str        # "system" | "user" | "assistant" | "tool"
    content: str
    name: str | None = None
    tool_call_id: str | None = None
    tool_calls: list[dict[str, Any]] | None = None

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {"role": self.role, "content": self.content}
        if self.name:
            d["name"] = self.name
        if self.tool_call_id:
            d["tool_call_id"] = self.tool_call_id
        if self.tool_calls:
            d["tool_calls"] = self.tool_calls
        return d


@dataclass
class LLMResponse:
    text: str = ""
    provider: str = ""
    model: str = ""
    input_tokens: int = 0
    output_tokens: int = 0
    cost_usd: float = 0.0
    latency_ms: float = 0.0
    finish_reason: str = "stop"
    tool_calls: list[dict[str, Any]] = field(default_factory=list)
    error: str | None = None

    @property
    def success(self) -> bool:
        return self.error is None

    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens


@dataclass
class LLMRequest:
    messages: list[Message]
    system_prompt: str | None = None
    max_tokens: int = 2048
    temperature: float = 0.7
    top_p: float = 1.0
    stream: bool = False
    tools: list[dict[str, Any]] | None = None
    tool_choice: str | dict[str, Any] = "auto"
    provider: LLMProvider = LLMProvider.AUTO
    model_override: str | None = None


# ──────────────────────────────────────────────────────────────────────────────
# LLM Router
# ──────────────────────────────────────────────────────────────────────────────


class LLMRouter:
    """
    Multi-provider LLM router.

    Usage::

        router = LLMRouter()
        response = await router.complete(request)

        async for chunk in router.stream(request):
            print(chunk, end="", flush=True)
    """

    def __init__(self) -> None:
        from app.core.config import settings  # noqa: PLC0415

        self._settings = settings
        self._openai_client: Any = None
        self._deepseek_client: Any = None
        self._ollama_base_url: str = "http://localhost:11434"

        # Runtime availability cache (checked lazily)
        self._provider_availability: dict[LLMProvider, bool] = {
            p: True for p in LLMProvider if p != LLMProvider.AUTO
        }

    # ── Public API ────────────────────────────────────────────────────────────

    async def complete(
        self,
        request: LLMRequest,
        max_retries: int = 3,
    ) -> LLMResponse:
        """
        Complete a request with automatic provider selection and retry.

        Args:
            request: LLMRequest with messages and generation params.
            max_retries: Number of retry attempts on transient failures.

        Returns:
            LLMResponse with generated text and usage metrics.
        """
        provider = self._select_provider(request)
        messages = self._prepare_messages(request)

        for attempt in range(max_retries + 1):
            try:
                t0 = time.perf_counter()
                response = await self._dispatch(provider, messages, request)
                response.latency_ms = (time.perf_counter() - t0) * 1000
                logger.info(
                    "llm_complete",
                    provider=provider.value,
                    model=response.model,
                    input_tokens=response.input_tokens,
                    output_tokens=response.output_tokens,
                    cost_usd=round(response.cost_usd, 6),
                    latency_ms=round(response.latency_ms, 1),
                )
                return response

            except Exception as exc:
                if attempt == max_retries:
                    logger.error(
                        "llm_complete_failed",
                        provider=provider.value,
                        error=str(exc),
                        attempts=attempt + 1,
                    )
                    return LLMResponse(error=str(exc), provider=provider.value)

                backoff = min(2 ** attempt, 30)
                logger.warning(
                    "llm_retry",
                    provider=provider.value,
                    attempt=attempt + 1,
                    backoff_s=backoff,
                    error=str(exc),
                )
                await asyncio.sleep(backoff)

                # Try next provider on persistent failure
                if attempt >= 1:
                    provider = self._fallback_provider(provider)

        return LLMResponse(error="Max retries exceeded")

    async def stream(
        self,
        request: LLMRequest,
    ) -> AsyncIterator[str]:
        """
        Stream text tokens as they arrive.

        Args:
            request: LLMRequest (stream will be forced to True).

        Yields:
            String text deltas.
        """
        request.stream = True
        provider = self._select_provider(request)
        messages = self._prepare_messages(request)

        try:
            async for chunk in self._dispatch_stream(provider, messages, request):
                yield chunk
        except Exception as exc:
            logger.error("llm_stream_error", provider=provider.value, error=str(exc))
            raise

    async def count_tokens(self, messages: list[Message], model: str = "gpt-4o") -> int:
        """Estimate token count for a list of messages using tiktoken."""
        try:
            import tiktoken  # noqa: PLC0415

            enc = tiktoken.encoding_for_model(model)
            total = 0
            for msg in messages:
                total += 4  # per-message overhead
                total += len(enc.encode(msg.content))
            return total
        except ImportError:
            # Rough estimate: 1 token ≈ 4 chars
            return sum(len(m.content) // 4 for m in messages)

    def estimate_cost(
        self,
        input_tokens: int,
        output_tokens: int,
        provider: LLMProvider,
    ) -> float:
        config = PROVIDER_CONFIGS.get(provider)
        if not config:
            return 0.0
        return (
            input_tokens / 1000 * config.cost_per_1k_input
            + output_tokens / 1000 * config.cost_per_1k_output
        )

    def truncate_context(
        self,
        messages: list[Message],
        max_tokens: int,
        preserve_system: bool = True,
    ) -> list[Message]:
        """
        Remove oldest messages until total token count fits within ``max_tokens``.
        Always preserves the system message and the latest user message.
        """
        result = list(messages)
        while True:
            total = sum(len(m.content) // 4 for m in result)
            if total <= max_tokens:
                break
            # Remove oldest non-system message
            for i, msg in enumerate(result):
                if preserve_system and msg.role == "system":
                    continue
                # Keep last user message
                if i == len(result) - 1:
                    break
                result.pop(i)
                break
            else:
                break
        return result

    # ── Provider dispatch ─────────────────────────────────────────────────────

    async def _dispatch(
        self,
        provider: LLMProvider,
        messages: list[dict[str, Any]],
        request: LLMRequest,
    ) -> LLMResponse:
        if provider == LLMProvider.OPENAI:
            return await self._openai_complete(messages, request)
        elif provider == LLMProvider.DEEPSEEK:
            return await self._deepseek_complete(messages, request)
        elif provider == LLMProvider.OLLAMA:
            return await self._ollama_complete(messages, request)
        raise ValueError(f"Unknown provider: {provider}")

    async def _dispatch_stream(
        self,
        provider: LLMProvider,
        messages: list[dict[str, Any]],
        request: LLMRequest,
    ) -> AsyncIterator[str]:
        if provider == LLMProvider.OPENAI:
            async for chunk in self._openai_stream(messages, request):
                yield chunk
        elif provider == LLMProvider.DEEPSEEK:
            async for chunk in self._deepseek_stream(messages, request):
                yield chunk
        elif provider == LLMProvider.OLLAMA:
            async for chunk in self._ollama_stream(messages, request):
                yield chunk
        else:
            raise ValueError(f"Unknown provider: {provider}")

    # ── OpenAI ────────────────────────────────────────────────────────────────

    def _get_openai_client(self) -> Any:
        if self._openai_client is None:
            from openai import AsyncOpenAI  # type: ignore[import]  # noqa: PLC0415

            self._openai_client = AsyncOpenAI(api_key=self._settings.OPENAI_API_KEY)
        return self._openai_client

    async def _openai_complete(
        self,
        messages: list[dict[str, Any]],
        request: LLMRequest,
    ) -> LLMResponse:
        client = self._get_openai_client()
        model = request.model_override or self._settings.OPENAI_MODEL_CHAT

        kwargs: dict[str, Any] = dict(
            model=model,
            messages=messages,
            max_tokens=request.max_tokens,
            temperature=request.temperature,
            top_p=request.top_p,
        )
        if request.tools:
            kwargs["tools"] = request.tools
            kwargs["tool_choice"] = request.tool_choice

        completion = await client.chat.completions.create(**kwargs)
        choice = completion.choices[0]
        usage = completion.usage

        tool_calls: list[dict[str, Any]] = []
        if choice.message.tool_calls:
            for tc in choice.message.tool_calls:
                tool_calls.append({
                    "id": tc.id,
                    "type": "function",
                    "function": {
                        "name": tc.function.name,
                        "arguments": tc.function.arguments,
                    },
                })

        resp = LLMResponse(
            text=choice.message.content or "",
            provider=LLMProvider.OPENAI.value,
            model=model,
            input_tokens=usage.prompt_tokens,
            output_tokens=usage.completion_tokens,
            finish_reason=choice.finish_reason,
            tool_calls=tool_calls,
        )
        resp.cost_usd = self.estimate_cost(resp.input_tokens, resp.output_tokens, LLMProvider.OPENAI)
        return resp

    async def _openai_stream(
        self,
        messages: list[dict[str, Any]],
        request: LLMRequest,
    ) -> AsyncIterator[str]:
        client = self._get_openai_client()
        model = request.model_override or self._settings.OPENAI_MODEL_CHAT

        stream = await client.chat.completions.create(
            model=model,
            messages=messages,
            max_tokens=request.max_tokens,
            temperature=request.temperature,
            stream=True,
        )
        async for chunk in stream:
            delta = chunk.choices[0].delta
            if delta.content:
                yield delta.content

    # ── DeepSeek ──────────────────────────────────────────────────────────────

    def _get_deepseek_client(self) -> Any:
        if self._deepseek_client is None:
            from openai import AsyncOpenAI  # type: ignore[import]  # noqa: PLC0415

            deepseek_key = getattr(self._settings, "DEEPSEEK_API_KEY", "")
            self._deepseek_client = AsyncOpenAI(
                api_key=deepseek_key,
                base_url="https://api.deepseek.com",
            )
        return self._deepseek_client

    async def _deepseek_complete(
        self,
        messages: list[dict[str, Any]],
        request: LLMRequest,
    ) -> LLMResponse:
        client = self._get_deepseek_client()
        model = request.model_override or "deepseek-chat"

        completion = await client.chat.completions.create(
            model=model,
            messages=messages,
            max_tokens=request.max_tokens,
            temperature=request.temperature,
        )
        choice = completion.choices[0]
        usage = completion.usage

        resp = LLMResponse(
            text=choice.message.content or "",
            provider=LLMProvider.DEEPSEEK.value,
            model=model,
            input_tokens=usage.prompt_tokens,
            output_tokens=usage.completion_tokens,
            finish_reason=choice.finish_reason,
        )
        resp.cost_usd = self.estimate_cost(resp.input_tokens, resp.output_tokens, LLMProvider.DEEPSEEK)
        return resp

    async def _deepseek_stream(
        self,
        messages: list[dict[str, Any]],
        request: LLMRequest,
    ) -> AsyncIterator[str]:
        client = self._get_deepseek_client()
        model = request.model_override or "deepseek-chat"

        stream = await client.chat.completions.create(
            model=model,
            messages=messages,
            max_tokens=request.max_tokens,
            temperature=request.temperature,
            stream=True,
        )
        async for chunk in stream:
            delta = chunk.choices[0].delta
            if delta.content:
                yield delta.content

    # ── Ollama ────────────────────────────────────────────────────────────────

    async def _ollama_complete(
        self,
        messages: list[dict[str, Any]],
        request: LLMRequest,
    ) -> LLMResponse:
        import aiohttp  # noqa: PLC0415

        model = request.model_override or PROVIDER_CONFIGS[LLMProvider.OLLAMA].model
        payload = {
            "model": model,
            "messages": messages,
            "stream": False,
            "options": {
                "temperature": request.temperature,
                "num_predict": request.max_tokens,
            },
        }

        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{self._ollama_base_url}/api/chat",
                json=payload,
                timeout=aiohttp.ClientTimeout(total=120),
            ) as resp:
                resp.raise_for_status()
                data = await resp.json()

        text = data.get("message", {}).get("content", "")
        eval_count = data.get("eval_count", 0)
        prompt_eval_count = data.get("prompt_eval_count", 0)

        return LLMResponse(
            text=text,
            provider=LLMProvider.OLLAMA.value,
            model=model,
            input_tokens=prompt_eval_count,
            output_tokens=eval_count,
            cost_usd=0.0,
        )

    async def _ollama_stream(
        self,
        messages: list[dict[str, Any]],
        request: LLMRequest,
    ) -> AsyncIterator[str]:
        import aiohttp  # noqa: PLC0415

        model = request.model_override or PROVIDER_CONFIGS[LLMProvider.OLLAMA].model
        payload = {
            "model": model,
            "messages": messages,
            "stream": True,
            "options": {
                "temperature": request.temperature,
                "num_predict": request.max_tokens,
            },
        }

        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{self._ollama_base_url}/api/chat",
                json=payload,
                timeout=aiohttp.ClientTimeout(total=120),
            ) as resp:
                resp.raise_for_status()
                async for raw_line in resp.content:
                    line = raw_line.decode().strip()
                    if not line:
                        continue
                    try:
                        data = json.loads(line)
                        content = data.get("message", {}).get("content", "")
                        if content:
                            yield content
                    except json.JSONDecodeError:
                        continue

    # ── Provider selection ────────────────────────────────────────────────────

    def _select_provider(self, request: LLMRequest) -> LLMProvider:
        if request.provider != LLMProvider.AUTO:
            return request.provider

        # Priority: DeepSeek (cheapest) → OpenAI → Ollama
        order = [LLMProvider.DEEPSEEK, LLMProvider.OPENAI, LLMProvider.OLLAMA]

        # If tools are required, only OpenAI reliably supports them
        if request.tools:
            order = [LLMProvider.OPENAI, LLMProvider.DEEPSEEK, LLMProvider.OLLAMA]

        for provider in order:
            if self._provider_availability.get(provider, False):
                config = PROVIDER_CONFIGS.get(provider)
                if config and config.available:
                    return provider

        return LLMProvider.OPENAI  # final fallback

    def _fallback_provider(self, current: LLMProvider) -> LLMProvider:
        """Return the next available provider after ``current``."""
        order = [LLMProvider.DEEPSEEK, LLMProvider.OPENAI, LLMProvider.OLLAMA]
        try:
            idx = order.index(current)
        except ValueError:
            idx = -1
        for i in range(idx + 1, len(order)):
            if self._provider_availability.get(order[i], True):
                return order[i]
        return LLMProvider.OPENAI

    def _prepare_messages(self, request: LLMRequest) -> list[dict[str, Any]]:
        """Build final message list, injecting system prompt if needed."""
        messages: list[dict[str, Any]] = []

        if request.system_prompt:
            messages.append({"role": "system", "content": request.system_prompt})

        for msg in request.messages:
            messages.append(msg.to_dict())

        return messages


# ──────────────────────────────────────────────────────────────────────────────
# Convenience singleton
# ──────────────────────────────────────────────────────────────────────────────

_router_instance: LLMRouter | None = None


def get_llm_router() -> LLMRouter:
    """Return the application-wide LLMRouter singleton."""
    global _router_instance
    if _router_instance is None:
        _router_instance = LLMRouter()
    return _router_instance
