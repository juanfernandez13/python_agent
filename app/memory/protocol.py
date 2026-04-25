from typing import Protocol

from app.memory.turn import MemoryTurn


class MemoryStore(Protocol):
    def add_turn(self, session_id: str, role: str, content: str) -> None: ...
    def get_history(self, session_id: str) -> list[MemoryTurn]: ...
