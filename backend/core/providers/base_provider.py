from abc import ABC, abstractmethod

class BaseProvider(ABC):
    @abstractmethod
    def complete(
        self,
        system_prompt: str,
        user_prompt: str,
        model: str = None,
        max_tokens: int = 8192,
        temperature: float = 0.2,
    ) -> str:
        """
        Send a chat completion request to the LLM provider.
        """
        pass

    @abstractmethod
    def is_available(self) -> bool:
        """
        Check if the provider is configured and available.
        """
        pass

    @abstractmethod
    def get_default_model(self) -> str:
        """
        Get the default model for this provider.
        """
        pass
