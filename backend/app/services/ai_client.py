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

from openai import AsyncOpenAI
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
        self.client = AsyncOpenAI(api_key=settings.openai_api_key)
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

                raw_content = response.choices[0].message.content
                if not raw_content:
                    raise AIClientError("Empty response from AI model")

                # Parse JSON
                try:
                    raw_json = json.loads(raw_content)
                except json.JSONDecodeError as e:
                    raise AIClientError(f"AI returned invalid JSON: {e}")

                # Validate with Pydantic
                try:
                    validated = output_schema.model_validate(raw_json)

                    if attempt == 0:
                        _stats["first_pass"] += 1
                        logger.info(f"Validation passed on first attempt for {output_schema.__name__}")
                    else:
                        _stats["retries"] += 1
                        logger.info(f"Validation passed on retry {attempt} for {output_schema.__name__}")

                    return validated

                except ValidationError as e:
                    last_error = str(e)
                    logger.warning(
                        f"Validation failed (attempt {attempt + 1}/{1 + self.max_retries}) "
                        f"for {output_schema.__name__}: {last_error}"
                    )

                    # Append error feedback for retry
                    current_user_prompt = user_prompt + RETRY_SUFFIX.format(errors=last_error)

            except AIClientError:
                raise
            except Exception as e:
                last_error = str(e)
                logger.error(f"AI call error (attempt {attempt + 1}): {last_error}")

        # All retries exhausted
        _stats["failures"] += 1
        raise AIClientError(
            f"Failed to generate valid output after {1 + self.max_retries} attempts. "
            f"Last error: {last_error}"
        )
