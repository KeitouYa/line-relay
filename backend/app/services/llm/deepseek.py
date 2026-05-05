from openai import OpenAI
from app.config import settings
from app.services.llm.base import LLMProvider


class DeepSeekProvider(LLMProvider):
    def __init__(self, model: str = "deepseek-v4-flash"):
        self.client = OpenAI(
            api_key=settings.deepseek_api_key,
            base_url="https://api.deepseek.com",
        )
        self.model = model

    def chat(
        self,
        system: str,
        user: str,
        max_tokens: int = 1000,
        temperature: float = 0.7,
    ) -> str:
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            max_tokens=max_tokens,
            temperature=temperature,
            extra_body={"thinking": {"type": "disabled"}},
        )
        return response.choices[0].message.content

    @property
    def name(self) -> str:
        return f"deepseek/{self.model}"