import os
import httpx
from openai import OpenAI
from backend.core.providers.base_provider import BaseProvider

class LocalProvider(BaseProvider):
    def __init__(self, api_key: str = None, base_url: str = None, default_model: str = None):
        # api_key is accepted but not strictly required for local, for signature uniformity
        self.custom_api_key = api_key
        self.custom_base_url = base_url
        self.custom_default_model = default_model
        self._client = None

    @property
    def client(self):
        base_url = self.custom_base_url or os.getenv("LOCAL_LLM_URL") or "http://localhost:11434/v1"
        api_key = self.custom_api_key or "local-no-key"
        if not self._client:
            self._client = OpenAI(
                api_key=api_key,
                base_url=base_url
            )
        return self._client

    def is_available(self) -> bool:
        base_url = self.custom_base_url or os.getenv("LOCAL_LLM_URL") or "http://localhost:11434/v1"
        try:
            url = base_url.rstrip("/") + "/models"
            if self.custom_base_url or os.getenv("LOCAL_LLM_URL"):
                return True
            response = httpx.get(url, timeout=0.5)
            return response.status_code == 200
        except Exception:
            return False

    def get_default_model(self) -> str:
        return self.custom_default_model or os.getenv("LOCAL_LLM_MODEL") or "llama3"

    def complete(
        self,
        system_prompt: str,
        user_prompt: str,
        model: str = None,
        max_tokens: int = 4096,
        temperature: float = 0.2,
    ) -> str:
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


