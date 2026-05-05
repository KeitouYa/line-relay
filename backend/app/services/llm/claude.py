from app.services.llm.base import LLMProvider


class ClaudeProvider(LLMProvider):
    """Claude Sonnet 4.6 实现 - 本 MVP 占位,未来切换时实装"""

    def __init__(self, model: str = "claude-sonnet-4-6"):
        self.model = model

    def chat(self, system: str, user: str, max_tokens: int = 1000, temperature: float = 0.7) -> str:
        raise NotImplementedError(
            "ClaudeProvider 是占位实现,切换到 Claude 时再实装。"
            "参考 deepseek.py,改用 anthropic SDK。"
        )

    @property
    def name(self) -> str:
        return f"claude/{self.model}"