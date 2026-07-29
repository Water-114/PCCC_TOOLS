from flask import current_app

from .claude_provider import ClaudeProvider
from .gemini_provider import GeminiProvider

PROVIDERS = {"claude", "gemini"}


def get_provider(name: str | None = None):
    cfg = current_app.config
    name = (name or cfg["AI_PROVIDER"]).lower()

    if name == "claude":
        return ClaudeProvider(cfg["ANTHROPIC_API_KEY"], cfg["ANTHROPIC_MODEL"])
    if name == "gemini":
        return GeminiProvider(cfg["GEMINI_API_KEY"], cfg["GEMINI_MODEL"])

    raise ValueError(f"Provider không hợp lệ: '{name}'. Chọn 1 trong {sorted(PROVIDERS)}.")
