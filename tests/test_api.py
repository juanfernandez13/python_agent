from fastapi.testclient import TestClient

from app.flow import FALLBACK_ANSWER, FlowResult, Orchestrator
from app.main import app
from app.memory import NullMemoryStore


class FakeOrchestrator:
    def __init__(self, result: FlowResult):
        self._result = result

    async def handle(self, message, session_id=None):
        return self._result


def _install_fake(result: FlowResult) -> None:
    app.state.orchestrator = FakeOrchestrator(result)


def test_health():
    with TestClient(app) as client:
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}


def test_messages_happy_path():
    with TestClient(app) as client:
        _install_fake(FlowResult("resposta", [{"section": "Composição"}]))
        response = client.post("/messages", json={"message": "O que é composição?"})
        assert response.status_code == 200
        body = response.json()
        assert body["answer"] == "resposta"
        assert body["sources"] == [{"section": "Composição"}]


def test_messages_fallback():
    with TestClient(app) as client:
        _install_fake(FlowResult(FALLBACK_ANSWER, []))
        response = client.post("/messages", json={"message": "pergunta sem escopo"})
        assert response.status_code == 200
        body = response.json()
        assert body["answer"] == FALLBACK_ANSWER
        assert body["sources"] == []


def test_messages_validation_rejects_blank():
    with TestClient(app) as client:
        response = client.post("/messages", json={"message": "   "})
        assert response.status_code == 422


def test_messages_validation_rejects_empty_string():
    with TestClient(app) as client:
        response = client.post("/messages", json={"message": ""})
        assert response.status_code == 422


def test_messages_validation_rejects_missing_message():
    with TestClient(app) as client:
        response = client.post("/messages", json={"session_id": "qualquer"})
        assert response.status_code == 422


def test_messages_validation_rejects_message_too_long():
    with TestClient(app) as client:
        oversized = "a" * 4001
        response = client.post("/messages", json={"message": oversized})
        assert response.status_code == 422


def test_messages_validation_rejects_session_id_with_invalid_chars():
    with TestClient(app) as client:
        response = client.post(
            "/messages",
            json={"message": "oi", "session_id": "tem espaço"},
        )
        assert response.status_code == 422


def test_messages_accepts_session_id():
    with TestClient(app) as client:
        _install_fake(FlowResult("r", [{"section": "Composição"}]))
        response = client.post(
            "/messages",
            json={"message": "oi", "session_id": "sessao-123"},
        )
        assert response.status_code == 200
