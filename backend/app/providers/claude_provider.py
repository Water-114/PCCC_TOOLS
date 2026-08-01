from .base import AIProvider, ProviderNotConfigured


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

    def generate_with_document(self, system_prompt: str, content_block: dict) -> str:
        if not self.api_key:
            raise ProviderNotConfigured(
                "Chưa cấu hình ANTHROPIC_API_KEY — thêm key vào backend/.env để dùng Claude."
            )

        import anthropic

        # Timeout client thấp hơn timeout của gunicorn (900s) một chút — để nếu Claude thật
        # sự chạy quá lâu, SDK tự ném lỗi rõ ràng (được bắt ở routes/aiho.py, trả về thông
        # báo lỗi sạch cho người dùng) THAY VÌ bị gunicorn cắt kết nối giữa chừng trước,
        # gây ra lỗi "Không kết nối được tới máy chủ AI" khó hiểu hơn nhiều.
        client = anthropic.Anthropic(api_key=self.api_key, timeout=870.0)
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
                "content": [
                    content_block,
                    {"type": "text", "text": "Hãy đọc bản vẽ trên và trả lời theo đúng định dạng JSON đã yêu cầu."},
                ],
            }],
        ) as stream:
            message = stream.get_final_message()
        return "".join(
            block.text for block in message.content if block.type == "text"
        )
