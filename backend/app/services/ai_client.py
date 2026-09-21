"""
AI Client

Wraps OpenAI API calls with:
- JSON mode enforcement
- Pydantic schema validation
- Automatic retry with error feedback
- Logging of validation pass/fail rates
"""

import json
import logging
from typing import TypeVar, Type

from openai import AsyncOpenAI, APIConnectionError, APIStatusError
from pydantic import BaseModel, ValidationError

from app.config import get_settings
from app.prompts.templates import RETRY_SUFFIX

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)

# Track validation stats for reliability metrics
_stats = {"total_calls": 0, "first_pass": 0, "retries": 0, "failures": 0}


def get_validation_stats() -> dict:
    """Return current validation pass rate stats."""
    total = _stats["total_calls"] or 1
    return {
        **_stats,
        "first_pass_rate": round(_stats["first_pass"] / total, 3),
        "retry_rate": round(_stats["retries"] / total, 3),
        "failure_rate": round(_stats["failures"] / total, 3),
    }


class AIClientError(Exception):
    pass


class AIClient:
    def __init__(self):
        settings = get_settings()
        self.client = AsyncOpenAI(api_key=settings.openai_api_key, max_retries=0)
        self.model = settings.ai_model
        self.temperature = settings.ai_temperature
        self.max_retries = settings.ai_max_retries

    async def generate_structured(
        self,
        system_prompt: str,
        user_prompt: str,
        output_schema: Type[T],
    ) -> T:
        """
        Call OpenAI with JSON mode, validate output against a Pydantic schema.
        Retries with error feedback on validation failure.

        Args:
            system_prompt: System message defining the task
            user_prompt: User message with the input data
            output_schema: Pydantic model class to validate against

        Returns:
            Validated Pydantic model instance

        Raises:
            AIClientError if all retries fail
        """
        _stats["total_calls"] += 1
        current_user_prompt = user_prompt
        last_error = None

        for attempt in range(1 + self.max_retries):
            try:
                # Call OpenAI with JSON mode
                response = await self.client.chat.completions.create(
                    model=self.model,
                    temperature=self.temperature,
                    response_format={"type": "json_object"},
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": current_user_prompt},
                    ],
                )

                raw_content = (
                    response.choices[0].message.content if response.choices else None
                )
                if not raw_content or not raw_content.strip():
                    raise AIClientError("Empty response from AI model")

                validated = output_schema.model_validate(json.loads(raw_content))
                _stats["first_pass" if attempt == 0 else "retries"] += 1
                logger.info("Validated %s on attempt %s", output_schema.__name__, attempt + 1)
                return validated

            except (AIClientError, json.JSONDecodeError, ValidationError) as e:
                # Do not echo model content into logs or validation feedback.
                if isinstance(e, ValidationError):
                    last_error = json.dumps(e.errors(include_input=False, include_url=False), default=str)
                elif isinstance(e, json.JSONDecodeError):
                    last_error = "AI returned invalid JSON"
                else:
                    last_error = str(e)
                current_user_prompt = user_prompt + RETRY_SUFFIX.format(errors=last_error)
                logger.warning("Invalid %s output on attempt %s", output_schema.__name__, attempt + 1)
            except APIConnectionError:
                last_error = "AI provider connection failed"
            except APIStatusError as e:
                last_error = f"AI provider returned HTTP {e.status_code}"
                if e.status_code not in {408, 409, 429} and e.status_code < 500:
                    break
            except Exception as e:
                # Unexpected errors are terminal; keep provider payloads out of API errors.
                last_error = f"Unexpected AI client error: {type(e).__name__}"
                break

        # All retries exhausted
        _stats["failures"] += 1
        raise AIClientError(
            f"Failed to generate valid output after {attempt + 1} attempts. "
            f"Last error: {last_error}"
        )
