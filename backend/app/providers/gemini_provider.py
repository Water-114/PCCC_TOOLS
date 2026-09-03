"""Provider Gemini — dùng google-genai, SDK chính thức hiện tại của Google cho
Gemini API (thay cho google-generativeai/`google.generativeai`, đã bị Google
khai tử: hỗ trợ dừng 2025-08-31, deprecated hẳn 2025-11-30). Batch 4 sub-bước 2.
"""

from . import resilience
from .base import AIProvider, GenerationResult, ProviderNotConfigured

# Khong co timeout rieng truoc day (chi dua vao gunicorn 900s cat cung) - gio dat
# rieng, NHO HON muc 870s cua Claude mot cach co chu dich: Gemini vua duoc bat
# retry_options (co the tu goi lai 1 lan khi loi mang/5xx/429) nen giu tran thap
# hon de tong thoi gian toi da (2 lan thu x timeout) van con bien do an toan duoi
# gunicorn 900s, ke ca khi cong don voi retry-repair schema o ai_reader_common.py.
_TIMEOUT_MS = 300_000  # 300s - gap ~2 lan thoi gian xu ly thuc te cham nhat (~150s, xem estimatedSeconds o frontend)
_RETRY_ATTEMPTS = 2  # toi thieu: 1 lan retry cho loi mang/429/5xx tam thoi (google-genai tu quyet dinh loai loi nao retry)


def _is_infra_error(exc: Exception) -> bool:
    import httpx
    from google.genai import errors

    if isinstance(exc, (httpx.TimeoutException, httpx.ConnectError)):
        return True
    if isinstance(exc, errors.ServerError):  # 5xx
        return True
    if isinstance(exc, errors.APIError) and getattr(exc, "code", None) == 429:
        return True
    return False


class GeminiProvider(AIProvider):
    name = "gemini"

    def __init__(self, api_key: str, model: str):
        self.api_key = api_key
        self.model = model

    def _client(self):
        from google import genai
        from google.genai import types

        return genai.Client(
            api_key=self.api_key,
            http_options=types.HttpOptions(
                timeout=_TIMEOUT_MS,
                retry_options=types.HttpRetryOptions(attempts=_RETRY_ATTEMPTS),
            ),
        )

    @staticmethod
    def _usage_dict(response) -> dict | None:
        meta = getattr(response, "usage_metadata", None)
        if meta is None:
            return None
        return {"input_tokens": meta.prompt_token_count, "output_tokens": meta.candidates_token_count}

    def generate(self, prompt: str) -> str:
        if not self.api_key:
            raise ProviderNotConfigured(
                "Chưa cấu hình GEMINI_API_KEY — thêm key vào backend/.env để dùng Gemini."
            )

        client = self._client()

        def _call():
            response = client.models.generate_content(model=self.model, contents=prompt)
            return response.text

        return resilience.guarded_call(self.name, _is_infra_error, _call)

    def generate_with_documents(self, system_prompt: str, content_blocks: list) -> GenerationResult:
        if not self.api_key:
            raise ProviderNotConfigured(
                "Chưa cấu hình GEMINI_API_KEY — thêm key vào backend/.env để dùng Gemini."
            )

        import base64

        from google.genai import types

        client = self._client()
        file_parts = [
            types.Part.from_bytes(
                data=base64.standard_b64decode(cb["source"]["data"]),
                mime_type=cb["source"]["media_type"],
            )
            for cb in content_blocks
        ]

        def _call():
            response = client.models.generate_content(
                model=self.model,
                contents=file_parts + ["Hãy đọc (các) bản vẽ trên và trả lời theo đúng định dạng JSON đã yêu cầu."],
                config=types.GenerateContentConfig(system_instruction=system_prompt),
            )
            return GenerationResult(text=response.text, usage=self._usage_dict(response))

        return resilience.guarded_call(self.name, _is_infra_error, _call)

    def generate_with_document(self, system_prompt: str, content_block: dict) -> GenerationResult:
        return self.generate_with_documents(system_prompt, [content_block])
