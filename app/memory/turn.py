from dataclasses import dataclass


@dataclass(frozen=True)
class MemoryTurn:
    role: str
    content: str
    timestamp: float
