import json
import time

import redis
from redis import exceptions as redis_exceptions

from app.core.logging import get_logger
from app.memory.turn import MemoryTurn

logger = get_logger(__name__)


class RedisMemoryStore:
    """Memória de sessão persistida em Redis.

    - Cada session_id vira uma List em `memory:{session_id}`.
    - LPUSH insere novos turnos no início; LTRIM mantém só os N mais recentes.
    - EXPIRE é renovado a cada escrita — TTL gerido pelo servidor.
    - Erros de Redis caem em silêncio com log: falha de memória não deve
      derrubar uma resposta do agente.
    """

    KEY_PREFIX: str = "memory:"

    def __init__(
        self,
        *,
        url: str,
        ttl_seconds: int = 900,
        max_turns: int = 6,
    ) -> None:
        self._ttl: int = ttl_seconds
        self._max_turns: int = max_turns
        self._client: redis.Redis = redis.Redis.from_url(url, decode_responses=True)

    def add_turn(self, session_id: str, role: str, content: str) -> None:
        if not session_id:
            return
        key = self._key(session_id)
        payload = json.dumps(
            {"role": role, "content": content, "ts": time.time()}
        )
        try:
            pipe = self._client.pipeline()
            pipe.lpush(key, payload)
            pipe.ltrim(key, 0, self._max_turns - 1)
            pipe.expire(key, self._ttl)
            pipe.execute()
        except redis_exceptions.RedisError as exc:
            logger.warning("redis_add_turn_failed session=%s err=%s", session_id, exc)

    def get_history(self, session_id: str) -> list[MemoryTurn]:
        if not session_id:
            return []
        key = self._key(session_id)
        try:
            items = self._client.lrange(key, 0, self._max_turns - 1)
        except redis_exceptions.RedisError as exc:
            logger.warning("redis_get_history_failed session=%s err=%s", session_id, exc)
            return []

        turns: list[MemoryTurn] = []
        for raw in reversed(items):
            try:
                data = json.loads(raw)
                turns.append(
                    MemoryTurn(
                        role=str(data["role"]),
                        content=str(data["content"]),
                        timestamp=float(data["ts"]),
                    )
                )
            except (json.JSONDecodeError, KeyError, TypeError, ValueError):
                continue
        return turns

    def ping(self) -> bool:
        try:
            return bool(self._client.ping())
        except redis_exceptions.RedisError:
            return False

    def _key(self, session_id: str) -> str:
        return f"{self.KEY_PREFIX}{session_id}"
