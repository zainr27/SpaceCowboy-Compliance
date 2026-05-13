from __future__ import annotations

import time
from typing import TypedDict, TypeVar

import structlog
from openai import AsyncOpenAI
from pydantic import BaseModel

from apps.api.config import get_settings

logger = structlog.get_logger(__name__)

TOutput = TypeVar("TOutput", bound=BaseModel)


class ClaudeCallMetadata(TypedDict):
    duration_ms: int
    input_tokens: int
    output_tokens: int
    model: str


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


def get_openai_client() -> AsyncOpenAI:
    """Lazy OpenAI client. One per process."""
    settings = get_settings()
    return AsyncOpenAI(api_key=settings.openai_api_key)


async def call_claude_structured(
    *,
    system_prompt: str,
    user_prompt: str,
    output_schema: type[TOutput],
    model: str = "gpt-4o",
    max_tokens: int = 4096,
    temperature: float = 0.0,
) -> tuple[TOutput, ClaudeCallMetadata]:
    """Call the LLM with a system prompt and user prompt, parse structured output.

    Returns (parsed_output, raw_metadata).
    Raises if the model returns invalid JSON or doesn't match the schema.
    """
    client = get_openai_client()

    schema_json = output_schema.model_json_schema()
    augmented_system = (
        f"{system_prompt}\n\n"
        f"You MUST respond with valid JSON matching this schema exactly:\n"
        f"```json\n{schema_json}\n```\n\n"
        f"Respond ONLY with the JSON object. No prose before or after. "
        f"No markdown code fences. Just the raw JSON."
    )

    start = time.monotonic()
    response = await client.chat.completions.create(
        model=model,
        max_tokens=max_tokens,
        temperature=temperature,
        messages=[
            {"role": "system", "content": augmented_system},
            {"role": "user", "content": user_prompt},
        ],
    )
    duration_ms = int((time.monotonic() - start) * 1000)

    text = (response.choices[0].message.content or "").strip()

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

    usage = response.usage
    input_tokens = usage.prompt_tokens if usage else 0
    output_tokens = usage.completion_tokens if usage else 0

    metadata: ClaudeCallMetadata = {
        "duration_ms": duration_ms,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "model": model,
    }

    logger.info(
        "llm_structured_complete",
        model=model,
        duration_ms=duration_ms,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        schema=output_schema.__name__,
    )

    return parsed, metadata
