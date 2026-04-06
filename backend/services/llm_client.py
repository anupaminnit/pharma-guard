"""
LLM provider abstraction — Protocol-based, switchable via LLM_PROVIDER env var.

Supported providers:
  - "anthropic" (default): Claude via Anthropic API
  - "azure":               GPT-4o via Azure OpenAI (data sovereignty for Baxter)

Usage:
    client = get_llm_client()
    text = client.create_message(
        model="claude-sonnet-4-5-20250514",
        messages=[{"role": "user", "content": "..."}],
        system="You are...",
        max_tokens=4096,
    )

Switching providers requires only changing LLM_PROVIDER in .env — no code changes.
"""

from __future__ import annotations

import os
from typing import Protocol, runtime_checkable

from dotenv import load_dotenv

load_dotenv()


@runtime_checkable
class LLMClient(Protocol):
    def create_message(
        self,
        model: str,
        messages: list[dict],
        system: str,
        max_tokens: int,
    ) -> str:
        """Send a message and return the response text."""
        ...


class AnthropicClient:
    """
    Claude via the Anthropic API.
    Requires: ANTHROPIC_API_KEY in environment.
    """

    def __init__(self) -> None:
        import anthropic
        self._client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))

    def create_message(self, model: str, messages: list[dict], system: str, max_tokens: int) -> str:
        response = self._client.messages.create(
            model=model,
            messages=messages,
            system=system,
            max_tokens=max_tokens,
        )
        return response.content[0].text


class AzureOpenAIClient:
    """
    GPT-4o (or configured model) via Azure OpenAI.
    Requires:
        AZURE_OPENAI_ENDPOINT  — e.g. https://baxter-ai.openai.azure.com/
        AZURE_OPENAI_KEY       — API key
        AZURE_OPENAI_DEPLOYMENT — deployment name, e.g. "gpt-4o"
        AZURE_OPENAI_API_VERSION — e.g. "2024-02-01"

    For data sovereignty: deploy Azure OpenAI in the same Azure region as the
    Baxter application (e.g. West Europe) and use a Private Endpoint so traffic
    never leaves the corporate network.
    """

    def __init__(self) -> None:
        try:
            from openai import AzureOpenAI
        except ImportError:
            raise RuntimeError(
                "openai package not installed. Run: pip install openai"
            )

        self._client = AzureOpenAI(
            azure_endpoint=os.environ["AZURE_OPENAI_ENDPOINT"],
            api_key=os.environ["AZURE_OPENAI_KEY"],
            api_version=os.environ.get("AZURE_OPENAI_API_VERSION", "2024-02-01"),
        )
        self._deployment = os.environ["AZURE_OPENAI_DEPLOYMENT"]

    def create_message(self, model: str, messages: list[dict], system: str, max_tokens: int) -> str:
        # Azure OpenAI uses the deployment name, not the model string
        full_messages = [{"role": "system", "content": system}] + messages
        response = self._client.chat.completions.create(
            model=self._deployment,
            messages=full_messages,
            max_tokens=max_tokens,
        )
        return response.choices[0].message.content


# ── Factory ───────────────────────────────────────────────────────────────────

_cached_client: LLMClient | None = None


def get_llm_client() -> LLMClient:
    """
    Return a cached LLM client instance.
    Provider selection via LLM_PROVIDER env var: "anthropic" (default) | "azure".
    """
    global _cached_client
    if _cached_client is not None:
        return _cached_client

    provider = os.environ.get("LLM_PROVIDER", "anthropic").lower()

    if provider == "azure":
        _cached_client = AzureOpenAIClient()
    else:
        _cached_client = AnthropicClient()

    return _cached_client


def reset_client_cache() -> None:
    """Force a new client to be created on next call. Useful for testing."""
    global _cached_client
    _cached_client = None
