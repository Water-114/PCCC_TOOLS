from .base import AIProvider, ProviderNotConfigured


class GeminiProvider(AIProvider):
    name = "gemini"

    def __init__(self, api_key: str, model: str):
        self.api_key = api_key
        self.model = model

    def generate(self, prompt: str) -> str:
        if not self.api_key:
            raise ProviderNotConfigured(
                "Chưa cấu hình GEMINI_API_KEY — thêm key vào backend/.env để dùng Gemini."
            )

        import google.generativeai as genai

        genai.configure(api_key=self.api_key)
        model = genai.GenerativeModel(self.model)
        response = model.generate_content(prompt)
        return response.text

    def generate_with_document(self, system_prompt: str, content_block: dict) -> str:
        if not self.api_key:
            raise ProviderNotConfigured(
                "Chưa cấu hình GEMINI_API_KEY — thêm key vào backend/.env để dùng Gemini."
            )

        import base64

        import google.generativeai as genai

        genai.configure(api_key=self.api_key)
        model = genai.GenerativeModel(self.model, system_instruction=system_prompt)
        source = content_block["source"]
        file_part = {
            "mime_type": source["media_type"],
            "data": base64.standard_b64decode(source["data"]),
        }
        response = model.generate_content([
            file_part,
            "Hãy đọc bản vẽ trên và trả lời theo đúng định dạng JSON đã yêu cầu.",
        ])
        return response.text
