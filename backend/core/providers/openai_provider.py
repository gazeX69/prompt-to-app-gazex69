import os
from openai import OpenAI
from backend.core.providers.base_provider import BaseProvider

class OpenAIProvider(BaseProvider):
    def __init__(self, api_key: str = None, base_url: str = None, default_model: str = None):
        self.custom_api_key = api_key
        self.custom_base_url = base_url
        self.custom_default_model = default_model
        self._client = None

    @property
    def client(self):
        api_key = self.custom_api_key or os.getenv("OPENAI_API_KEY")
        base_url = self.custom_base_url or os.getenv("OPENAI_BASE_URL")  # support custom base URL if provided
        if not self._client and api_key:
            if base_url:
                self._client = OpenAI(api_key=api_key, base_url=base_url)
            else:
                self._client = OpenAI(api_key=api_key)
        return self._client

    def is_available(self) -> bool:
        api_key = self.custom_api_key or os.getenv("OPENAI_API_KEY")
        return bool(api_key)

    def get_default_model(self) -> str:
        return self.custom_default_model or "gpt-4o"

    def complete(
        self,
        system_prompt: str,
        user_prompt: str,
        model: str = None,
        max_tokens: int = 4096,
        temperature: float = 0.2,
    ) -> str:
        if not self.is_available():
            raise ValueError("OpenAI Provider is not configured (missing OPENAI_API_KEY)")
        
        target_model = model or self.get_default_model()
        response = self.client.chat.completions.create(
            model=target_model,
            max_tokens=max_tokens,
            temperature=temperature,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ]
        )
        self.last_prompt_tokens = response.usage.prompt_tokens if response.usage else None
        self.last_completion_tokens = response.usage.completion_tokens if response.usage else None
        return response.choices[0].message.content


