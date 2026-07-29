from abc import ABC, abstractmethod


class AIProvider(ABC):
    name: str = "base"

    @abstractmethod
    def generate(self, prompt: str) -> str:
        """Tra ve van ban tra loi cho prompt. Raise ProviderNotConfigured neu thieu key."""
        raise NotImplementedError


class ProviderNotConfigured(Exception):
    """API key cho provider nay chua duoc cau hinh trong .env."""
