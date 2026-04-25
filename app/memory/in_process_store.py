import time
from collections import deque

from app.memory.turn import MemoryTurn


class InProcessMemoryStore:
    """Memória in-process por session_id.

    - TTL por turno: turnos expirados são removidos no acesso.
    - Janela curta: mantém apenas os N turnos mais recentes.
    - Isolamento: cada session_id vive em sua própria deque.
    """

    def __init__(self, *, ttl_seconds: int = 900, max_turns: int = 6) -> None:
        self._ttl: int = ttl_seconds
        self._max_turns: int = max_turns
        self._store: dict[str, deque[MemoryTurn]] = {}

    def add_turn(self, session_id: str, role: str, content: str) -> None:
        if not session_id:
            return
        self._prune(session_id)
        turns = self._store.setdefault(session_id, deque(maxlen=self._max_turns))
        turns.append(MemoryTurn(role=role, content=content, timestamp=time.time()))

    def get_history(self, session_id: str) -> list[MemoryTurn]:
        if not session_id or session_id not in self._store:
            return []
        self._prune(session_id)
        return list(self._store.get(session_id, ()))

    def _prune(self, session_id: str) -> None:
        turns = self._store.get(session_id)
        if not turns:
            return
        now = time.time()
        fresh: deque[MemoryTurn] = deque(
            (t for t in turns if now - t.timestamp <= self._ttl),
            maxlen=self._max_turns,
        )
        if fresh:
            self._store[session_id] = fresh
        else:
            self._store.pop(session_id, None)
