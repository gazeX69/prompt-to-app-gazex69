import os
import httpx
from backend.core.providers.base_provider import BaseProvider

class AnthropicProvider(BaseProvider):
    def __init__(self, api_key: str = None, base_url: str = None, default_model: str = None):
        self.custom_api_key = api_key
        self.custom_base_url = base_url
        self.custom_default_model = default_model

    def is_available(self) -> bool:
        api_key = self.custom_api_key or os.getenv("ANTHROPIC_API_KEY")
        return bool(api_key)

    def get_default_model(self) -> str:
        return self.custom_default_model or "claude-3-5-sonnet-20241022"

    def complete(
        self,
        system_prompt: str,
        user_prompt: str,
        model: str = None,
        max_tokens: int = 4096,
        temperature: float = 0.2,
    ) -> str:
        if not self.is_available():
            raise ValueError("Anthropic Provider is not configured (missing ANTHROPIC_API_KEY)")
        
        target_model = model or self.get_default_model()
        api_key = self.custom_api_key or os.getenv("ANTHROPIC_API_KEY")
        base_url = self.custom_base_url or "https://api.anthropic.com/v1/messages"
        
        headers = {
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json"
        }
        
        payload = {
            "model": target_model,
            "max_tokens": max_tokens,
            "system": system_prompt,
            "messages": [
                {"role": "user", "content": user_prompt}
            ],
            "temperature": temperature
        }
        
        # Use sync client for complete
        with httpx.Client(timeout=60.0) as client:
            response = client.post(base_url, headers=headers, json=payload)
            response.raise_for_status()
            data = response.json()
            usage = data.get("usage", {})
            self.last_prompt_tokens = usage.get("input_tokens")
            self.last_completion_tokens = usage.get("output_tokens")
            return data["content"][0]["text"]


