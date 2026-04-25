import json

import fakeredis
import pytest

from app.memory import RedisMemoryStore


@pytest.fixture
def store(monkeypatch) -> RedisMemoryStore:
    fake = fakeredis.FakeRedis(decode_responses=True)
    monkeypatch.setattr(
        "app.memory.redis_store.redis.Redis.from_url",
        lambda *args, **kwargs: fake,
    )
    return RedisMemoryStore(url="redis://unused", ttl_seconds=900, max_turns=4)


def test_add_and_get_single_turn(store: RedisMemoryStore) -> None:
    store.add_turn("sess-1", "user", "olá")

    history = store.get_history("sess-1")

    assert len(history) == 1
    assert history[0].role == "user"
    assert history[0].content == "olá"
    assert history[0].timestamp > 0


def test_history_returns_chronological_order(store: RedisMemoryStore) -> None:
    store.add_turn("sess-1", "user", "primeira")
    store.add_turn("sess-1", "assistant", "segunda")
    store.add_turn("sess-1", "user", "terceira")

    history = store.get_history("sess-1")

    assert [t.content for t in history] == ["primeira", "segunda", "terceira"]


def test_max_turns_trims_oldest(store: RedisMemoryStore) -> None:
    for i in range(6):
        store.add_turn("sess-1", "user", f"msg-{i}")

    history = store.get_history("sess-1")

    assert len(history) == 4
    assert [t.content for t in history] == ["msg-2", "msg-3", "msg-4", "msg-5"]


def test_ttl_is_set_on_writes(store: RedisMemoryStore) -> None:
    store.add_turn("sess-1", "user", "teste")

    ttl = store._client.ttl("memory:sess-1")
    assert 0 < ttl <= 900


def test_isolates_by_session_id(store: RedisMemoryStore) -> None:
    store.add_turn("sess-A", "user", "só da A")
    store.add_turn("sess-B", "user", "só da B")

    history_a = store.get_history("sess-A")
    history_b = store.get_history("sess-B")

    assert [t.content for t in history_a] == ["só da A"]
    assert [t.content for t in history_b] == ["só da B"]


def test_empty_session_id_is_ignored(store: RedisMemoryStore) -> None:
    store.add_turn("", "user", "fantasma")

    assert store.get_history("") == []
    assert store._client.keys("memory:*") == []


def test_get_history_unknown_session_returns_empty(store: RedisMemoryStore) -> None:
    assert store.get_history("nunca-existiu") == []


def test_corrupted_json_is_skipped(store: RedisMemoryStore) -> None:
    store.add_turn("sess-1", "user", "válido")
    store._client.lpush("memory:sess-1", "{não é json}")

    history = store.get_history("sess-1")

    assert len(history) == 1
    assert history[0].content == "válido"


def test_missing_field_in_payload_is_skipped(store: RedisMemoryStore) -> None:
    store._client.lpush("memory:sess-1", json.dumps({"role": "user"}))

    assert store.get_history("sess-1") == []


def test_ping_returns_true_when_alive(store: RedisMemoryStore) -> None:
    assert store.ping() is True
