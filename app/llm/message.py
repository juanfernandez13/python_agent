from dataclasses import dataclass


@dataclass(frozen=True)
class LLMMessage:
    role: str
    content: str
