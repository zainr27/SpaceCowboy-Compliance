from __future__ import annotations

import time
from typing import TypeVar

import anthropic
import structlog
from pydantic import BaseModel

from apps.api.config import get_settings

logger = structlog.get_logger(__name__)

TOutput = TypeVar("TOutput", bound=BaseModel)


class AgentMetadata(BaseModel):
    """Provenance for an agent run."""

    agent_name: str
    model: str
    duration_ms: int
    input_tokens: int | None = None
    output_tokens: int | None = None
    retrieval_chunks: int = 0
    retrieval_ms: int = 0


class AgentResult(BaseModel):
    """Wrapper around any agent's structured output."""

    output: BaseModel
    metadata: AgentMetadata


def get_anthropic_client() -> anthropic.AsyncAnthropic:
    """Lazy Anthropic client. One per process."""
    settings = get_settings()
    return anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)


async def call_claude_structured(
    *,
    system_prompt: str,
    user_prompt: str,
    output_schema: type[TOutput],
    model: str = "claude-sonnet-4-5",
    max_tokens: int = 4096,
    temperature: float = 0.0,
) -> tuple[TOutput, dict[str, object]]:
    """Call Claude with a system prompt and user prompt, parse structured output.

    Returns (parsed_output, raw_metadata).
    Raises if the model returns invalid JSON or doesn't match the schema.
    """
    client = get_anthropic_client()

    schema_json = output_schema.model_json_schema()
    augmented_system = (
        f"{system_prompt}\n\n"
        f"You MUST respond with valid JSON matching this schema exactly:\n"
        f"```json\n{schema_json}\n```\n\n"
        f"Respond ONLY with the JSON object. No prose before or after. "
        f"No markdown code fences. Just the raw JSON."
    )

    start = time.monotonic()
    response = await client.messages.create(
        model=model,
        max_tokens=max_tokens,
        temperature=temperature,
        system=augmented_system,
        messages=[{"role": "user", "content": user_prompt}],
    )
    duration_ms = int((time.monotonic() - start) * 1000)

    text = "".join(block.text for block in response.content if block.type == "text").strip()

    if text.startswith("```"):
        lines = text.split("\n")
        text = "\n".join(lines[1:-1]) if lines[-1].startswith("```") else "\n".join(lines[1:])

    try:
        parsed = output_schema.model_validate_json(text)
    except Exception as e:
        logger.error(
            "agent_output_parse_failed",
            error=str(e),
            raw_text=text[:500],
            schema=output_schema.__name__,
        )
        raise

    metadata = {
        "duration_ms": duration_ms,
        "input_tokens": response.usage.input_tokens,
        "output_tokens": response.usage.output_tokens,
        "model": model,
    }

    logger.info(
        "claude_structured_complete",
        model=model,
        duration_ms=duration_ms,
        input_tokens=response.usage.input_tokens,
        output_tokens=response.usage.output_tokens,
        schema=output_schema.__name__,
    )

    return parsed, metadata
