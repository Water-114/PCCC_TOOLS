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

        client = anthropic.Anthropic(api_key=self.api_key)
        # max_tokens lớn (đủ cho ~50 dòng tiêu chí + kiến nghị) buộc phải dùng streaming —
        # request non-streaming của Anthropic giới hạn 10 phút, dễ bị từ chối ở mức token này.
        # effort "medium" (thay vì "high"): trên Render, request hay bị ngắt ở khoảng 6 phút
        # do giới hạn ở tầng proxy trung gian (không chỉnh được qua gunicorn --timeout) —
        # giảm effort giúp Claude trả lời nhanh hơn hẳn, vẫn đủ chính xác cho việc trích xuất
        # theo tiêu chí có cấu trúc sẵn (không phải suy luận sáng tạo mở).
        with client.messages.stream(
            model=self.model,
            max_tokens=32000,
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
