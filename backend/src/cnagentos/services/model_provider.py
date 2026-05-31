from collections.abc import AsyncIterator
from dataclasses import dataclass

from openai import AsyncOpenAI


@dataclass(frozen=True)
class ModelProviderUsage:
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    total_tokens: int | None = None


@dataclass(frozen=True)
class ModelProviderResponse:
    reply: str
    usage: ModelProviderUsage


class InvalidModelResponse(ValueError):
    pass


class ModelProviderClient:
    def __init__(
        self,
        api_key: str,
        base_url: str,
        timeout_seconds: int,
    ) -> None:
        self.client = AsyncOpenAI(
            api_key=api_key,
            base_url=base_url,
            timeout=timeout_seconds,
            max_retries=0,
        )

    async def complete_chat(self, model_name: str, message: str) -> ModelProviderResponse:
        return await self.complete_chat_with_messages(
            model_name, [{"role": "user", "content": message}],
        )

    async def complete_chat_with_messages(
        self, model_name: str, messages: list[dict],
    ) -> ModelProviderResponse:
        """Complete a chat with a full messages list (system, user, assistant)."""
        try:
            response = await self.client.chat.completions.create(
                model=model_name,
                messages=messages,
                stream=False,
            )
        finally:
            await self.client.close()

        choices = response.choices or []
        if not choices or choices[0].message.content is None:
            raise InvalidModelResponse("missing assistant message content")

        usage = response.usage
        return ModelProviderResponse(
            reply=choices[0].message.content,
            usage=ModelProviderUsage(
                prompt_tokens=usage.prompt_tokens if usage else None,
                completion_tokens=usage.completion_tokens if usage else None,
                total_tokens=usage.total_tokens if usage else None,
            ),
        )

    async def stream_chat(self, model_name: str, message: str) -> AsyncIterator[dict]:
        try:
            stream = await self.client.chat.completions.create(
                model=model_name,
                messages=[{"role": "user", "content": message}],
                stream=True,
            )
            async for chunk in stream:
                yield chunk.model_dump(mode="json", exclude_none=True)
        finally:
            await self.client.close()
