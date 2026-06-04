"""
AI provider service.

Wraps the OpenAI-compatible Qwen/DashScope client.
Single responsibility: make API calls and return raw string content.
All prompt construction happens in app/prompts/templates.py.
All response parsing happens in app/agent/parser.py.
"""

import os
from dotenv import load_dotenv
from openai import OpenAI
from backend.core.provider_registry import ProviderRegistry

# Load .env BEFORE creating client
load_dotenv()

# Keep backward-compatible default client for legacy scripts if needed
_client = None
def get_legacy_client():
    global _client
    if _client is None:
        _client = OpenAI(
            api_key=os.getenv("DASHSCOPE_API_KEY"),
            base_url="https://dashscope-intl.aliyuncs.com/compatible-mode/v1",
        )
    return _client

DEFAULT_MODEL = "qwen-plus"
DEFAULT_MAX_TOKENS = 8192
DEFAULT_TEMPERATURE = 0.2  # Lower = more deterministic code output


def complete(
    system_prompt: str,
    user_prompt: str,
    model: str = DEFAULT_MODEL,
    max_tokens: int = DEFAULT_MAX_TOKENS,
    temperature: float = DEFAULT_TEMPERATURE,
) -> str:
    """
    Send a chat completion request and return the raw string response.
    Routes dynamically through the selected/active provider in ProviderRegistry,
    with automatic failover fallback switching support.
    """
    registry = ProviderRegistry.get_instance()
    return registry.complete_with_fallback(
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        model=model,
        max_tokens=max_tokens,
        temperature=temperature,
    )


