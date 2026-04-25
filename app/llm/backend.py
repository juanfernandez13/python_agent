from typing import Protocol

from app.llm.message import LLMMessage


class LLMBackend(Protocol):
    async def generate(self, messages: list[LLMMessage]) -> str: ...
