from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional


@dataclass
class GenerationResult:
    """Ket qua 1 lan goi generate_with_document() - tach rieng van ban tra loi
    va usage (so token) de ai_reader_common ghi log ma khong doi kieu tra ve
    cua generate() (van la str, khong lien quan diem doc ban ve)."""

    text: str
    usage: Optional[dict] = None  # vd {"input_tokens": .., "output_tokens": ..} - None neu provider khong tra duoc


class AIProvider(ABC):
    name: str = "base"

    @abstractmethod
    def generate(self, prompt: str) -> str:
        """Tra ve van ban tra loi cho prompt. Raise ProviderNotConfigured neu thieu key."""
        raise NotImplementedError


class ProviderNotConfigured(Exception):
    """API key cho provider nay chua duoc cau hinh trong .env."""
