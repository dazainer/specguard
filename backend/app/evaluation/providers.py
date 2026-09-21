"""Provider boundary for executable generation; the manual API keeps its own policy."""
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from openai import APIConnectionError, APIStatusError

from app.evaluation.manifest import GenerationConfig
from app.services.ai_client import AIClient


@dataclass
class Completion:
    text: str
    input_tokens: int | None = None
    output_tokens: int | None = None
    model: str | None = None
    fingerprint: str | None = None


class ProviderFailure(Exception):
    def __init__(self, category: str, retryable: bool):
        self.category, self.retryable = category, retryable
        super().__init__(category)


class Provider(Protocol):
    async def complete(self, system: str, user: str, config: GenerationConfig) -> Completion: ...


class FixtureProvider:
    def __init__(self, path: Path):
        if path.is_symlink() or path.stat().st_size > 2 * 1024 * 1024:
            raise ValueError('Invalid fixture file')
        self.text = path.read_text()

    async def complete(self, system, user, config):
        return Completion(self.text, model='handwritten-fixture-v1')


class OpenAIProvider:
    """Use the existing AI client's SDK transport, with evaluator-owned retries."""
    def __init__(self):
        self.ai = AIClient()

    async def complete(self, system, user, config):
        try:
            response = await self.ai.client.chat.completions.create(
                model=config.model, temperature=config.temperature, seed=config.seed,
                response_format={'type': 'json_object'}, max_tokens=4096, timeout=60,
                messages=[{'role': 'system', 'content': system}, {'role': 'user', 'content': user}],
            )
            return Completion(
                response.choices[0].message.content or '' if response.choices else '',
                response.usage.prompt_tokens if response.usage else None,
                response.usage.completion_tokens if response.usage else None,
                response.model, response.system_fingerprint,
            )
        except APIConnectionError as error:
            raise ProviderFailure('provider_connection', True) from error
        except APIStatusError as error:
            retryable = error.status_code in {408, 409, 429} or error.status_code >= 500
            raise ProviderFailure(f'provider_http_{error.status_code}', retryable) from error

    async def close(self):
        await self.ai.client.close()
