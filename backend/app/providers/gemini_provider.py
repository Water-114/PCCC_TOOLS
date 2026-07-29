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
