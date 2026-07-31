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
        # 64000 (thay vì 32000): với bản vẽ thật phức tạp, phần "suy nghĩ" ẩn (thinking) của
        # Claude có thể chiếm phần lớn max_tokens, khiến phần JSON hiển thị (47 tiêu chí +
        # kiến nghị) bị cắt giữa chừng dù effort đã giảm — tăng tổng ngân sách token để còn
        # đủ chỗ cho phần JSON hiển thị hoàn tất, dù thinking dùng bao nhiêu đi nữa.
        with client.messages.stream(
            model=self.model,
            max_tokens=64000,
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
