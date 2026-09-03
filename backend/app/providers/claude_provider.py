from . import resilience
from .base import AIProvider, GenerationResult, ProviderNotConfigured

# Duoi timeout cua gunicorn (900s) mot chut - de neu Claude that su chay qua lau,
# SDK tu nem loi ro rang (duoc bat o routes/aiho.py) THAY VI bi gunicorn cat ket
# noi giua chung truoc, gay ra loi "Khong ket noi duoc toi may chu AI" kho hieu hon.
_TIMEOUT_SECONDS = 870.0
# "Toi thieu" theo dung yeu cau Batch 4 sub-buoc 2 - SDK anthropic tu quyet dinh
# loai loi nao dang retry (APIConnectionError/APITimeoutError, 429, >=500) va tu
# backoff giua cac lan; chi giam so lan retry (mac dinh SDK la 2) de gioi han rui
# ro cong don thoi gian khi ket hop voi retry-repair schema (co the goi lai them
# 1 lan o ai_reader_common.py).
_MAX_RETRIES = 1


def _is_infra_error(exc: Exception) -> bool:
    import anthropic

    if isinstance(exc, anthropic.APIConnectionError):  # bao gom ca APITimeoutError
        return True
    if isinstance(exc, anthropic.APIStatusError):
        return exc.status_code == 429 or exc.status_code >= 500
    return False


class ClaudeProvider(AIProvider):
    name = "claude"

    def __init__(self, api_key: str, model: str):
        self.api_key = api_key
        self.model = model

    def generate(self, prompt: str) -> str:
        if not self.api_key:
            raise ProviderNotConfigured(
                "Chưa cấu hình ANTHROPIC_API_KEY — thêm key vào backend/.env để dùng Claude."
            )

        import anthropic

        client = anthropic.Anthropic(api_key=self.api_key)
        message = client.messages.create(
            model=self.model,
            max_tokens=1024,
            thinking={"type": "disabled"},
            messages=[{"role": "user", "content": prompt}],
        )
        return "".join(
            block.text for block in message.content if block.type == "text"
        )

    def generate_with_documents(self, system_prompt: str, content_blocks: list) -> GenerationResult:
        if not self.api_key:
            raise ProviderNotConfigured(
                "Chưa cấu hình ANTHROPIC_API_KEY — thêm key vào backend/.env để dùng Claude."
            )

        import anthropic

        client = anthropic.Anthropic(api_key=self.api_key, timeout=_TIMEOUT_SECONDS, max_retries=_MAX_RETRIES)

        def _call():
            # max_tokens = 128000 (mức tối đa Claude Sonnet 5 hỗ trợ khi dùng streaming): đây là
            # NGÂN SÁCH TỐI ĐA được phép dùng, không phải mức luôn phải tốn — chi phí tính theo
            # số token thực sự sinh ra, không theo mức trần này. Đặt cao để loại hẳn rủi ro bị
            # cắt ngang JSON giữa chừng (đã gặp 2 lần ở mức thấp hơn) cho các bản vẽ phức tạp.
            with client.messages.stream(
                model=self.model,
                max_tokens=128000,
                thinking={"type": "adaptive"},
                output_config={"effort": "medium"},
                system=system_prompt,
                messages=[{
                    "role": "user",
                    "content": content_blocks + [
                        {"type": "text", "text": "Hãy đọc (các) bản vẽ trên và trả lời theo đúng định dạng JSON đã yêu cầu."},
                    ],
                }],
            ) as stream:
                message = stream.get_final_message()
            text = "".join(block.text for block in message.content if block.type == "text")
            usage = None
            if message.usage is not None:
                usage = {"input_tokens": message.usage.input_tokens, "output_tokens": message.usage.output_tokens}
            return GenerationResult(text=text, usage=usage)

        return resilience.guarded_call(self.name, _is_infra_error, _call)

    def generate_with_document(self, system_prompt: str, content_block: dict) -> GenerationResult:
        return self.generate_with_documents(system_prompt, [content_block])
