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

# Client is constructed once at import time.
# If DASHSCOPE_API_KEY is missing, OpenAI() will raise at call time, not import time.
# Load .env BEFORE creating client
load_dotenv()

_client = OpenAI(
    api_key=os.getenv("DASHSCOPE_API_KEY"),
    base_url="https://dashscope-intl.aliyuncs.com/compatible-mode/v1",
)

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

    Args:
        system_prompt: The system role message.
        user_prompt:   The user role message.
        model:         Model identifier.
        max_tokens:    Maximum tokens in the response.
        temperature:   Sampling temperature (0 = deterministic).

    Returns:
        Raw string content from the model.

    Raises:
        Any openai.* exception on API failure — callers handle these.
    """
    response = _client.chat.completions.create(
        model=model,
        max_tokens=max_tokens,
        temperature=temperature,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
    )
    return response.choices[0].message.content
