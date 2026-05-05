from app.config import settings
from app.services.llm.base import LLMProvider
from app.services.llm.deepseek import DeepSeekProvider
from app.services.llm.claude import ClaudeProvider


def get_llm_provider() -> LLMProvider:
    name = settings.llm_provider  # 默认 "deepseek-flash"
    if name == "deepseek-flash":
        return DeepSeekProvider(model="deepseek-v4-flash")
    if name == "deepseek-pro":
        return DeepSeekProvider(model="deepseek-v4-pro")
    if name == "claude":
        return ClaudeProvider()
    raise ValueError(f"未知 LLM provider: {name}")