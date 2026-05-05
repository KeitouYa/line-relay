from abc import ABC, abstractmethod


class LLMProvider(ABC):
    """LLM 抽象基类,所有 provider 实现这个接口"""

    @abstractmethod
    def chat(
        self,
        system: str,
        user: str,
        max_tokens: int = 1000,
        temperature: float = 0.7,
    ) -> str:
        """单轮对话,返回 LLM 文本输出"""
        pass

    @property
    @abstractmethod
    def name(self) -> str:
        """provider 名字,用于日志"""
        pass