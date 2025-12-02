"""LLM provider abstraction — wraps litellm for provider-agnostic completions."""

from __future__ import annotations

import json
import logging
from typing import Any

import litellm

from codewise.models import CodewiseConfig

litellm.drop_params = True  # ignore unsupported params per-provider
logger = logging.getLogger("codewise.llm")


# ── Model presets per provider ──────────────────────────────────────

DEFAULT_MODELS: dict[str, str] = {
    "openai": "gpt-4o-mini",
    "anthropic": "claude-sonnet-4-20250514",
    "google": "gemini/gemini-2.0-flash",
    "ollama": "ollama/llama3.1",
    "azure": "azure/gpt-4o-mini",
    "bedrock": "bedrock/anthropic.claude-sonnet-4-20250514-v2:0",
}


def _build_litellm_kwargs(config: CodewiseConfig) -> dict[str, Any]:
    """Build kwargs dict for litellm.completion from config."""
    kwargs: dict[str, Any] = {
        "model": config.model,
        "temperature": config.temperature,
        "max_tokens": config.max_tokens,
    }
    if config.api_key:
        kwargs["api_key"] = config.api_key
    if config.api_base:
        kwargs["api_base"] = config.api_base
    return kwargs


async def completion(
    messages: list[dict[str, str]],
    config: CodewiseConfig,
    response_format: dict | None = None,
) -> tuple[str, int]:
    """Send messages to the configured LLM and return (response_text, tokens_used).

    Uses litellm for provider-agnostic routing.  Supports OpenAI, Anthropic,
    Google Gemini, Ollama, Azure OpenAI, and AWS Bedrock out of the box.
    """
    kwargs = _build_litellm_kwargs(config)
    kwargs["messages"] = messages
    if response_format:
        kwargs["response_format"] = response_format

    logger.debug("LLM request: model=%s messages=%d", config.model, len(messages))

    response = await litellm.acompletion(**kwargs)

    text = response.choices[0].message.content or ""
    tokens = response.usage.total_tokens if response.usage else 0
    logger.debug("LLM response: tokens=%d len=%d", tokens, len(text))
    return text, tokens


async def completion_json(
    messages: list[dict[str, str]],
    config: CodewiseConfig,
) -> tuple[dict | list, int]:
    """Like completion() but parses response as JSON.

    Attempts JSON mode first (if provider supports it), falls back to
    extracting JSON from markdown code blocks.
    """
    text, tokens = await completion(
        messages,
        config,
        response_format={"type": "json_object"},
    )
    try:
        return json.loads(text), tokens
    except json.JSONDecodeError:
        # Try extracting from ```json ... ``` blocks
        if "```json" in text:
            start = text.index("```json") + 7
            end = text.index("```", start)
            return json.loads(text[start:end].strip()), tokens
        if "```" in text:
            start = text.index("```") + 3
            end = text.index("```", start)
            return json.loads(text[start:end].strip()), tokens
        raise
