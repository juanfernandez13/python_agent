from app.memory.turn import MemoryTurn


class NullMemoryStore:
    """Memória desativada: nunca guarda, sempre retorna vazio."""

    def add_turn(self, session_id: str, role: str, content: str) -> None:
        return

    def get_history(self, session_id: str) -> list[MemoryTurn]:
        return []
