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
        message = client.messages.create(
            model=self.model,
            max_tokens=4096,
            system=system_prompt,
            messages=[{
                "role": "user",
                "content": [
                    content_block,
                    {"type": "text", "text": "Hãy đọc bản vẽ trên và trả lời theo đúng định dạng JSON đã yêu cầu."},
                ],
            }],
        )
        return "".join(
            block.text for block in message.content if block.type == "text"
        )
