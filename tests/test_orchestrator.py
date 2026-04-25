import pytest

from app.flow import FALLBACK_ANSWER, Orchestrator
from app.llm import LLMError
from app.memory import InProcessMemoryStore, NullMemoryStore
from app.tools import SectionMatch


class FakeTool:
    def __init__(self, result=None, raise_exc=None):
        self._result = result or []
        self._raise = raise_exc

    async def search(self, query: str):
        if self._raise:
            raise self._raise
        return list(self._result)


def _make_llm(text="Resposta OK", raise_exc=None):
    async def _gen(messages):
        if raise_exc:
            raise raise_exc
        return text
    return _gen


@pytest.mark.asyncio
async def test_fallback_when_tool_returns_empty():
    orch = Orchestrator(tool=FakeTool([]), llm_generate=_make_llm(), memory=NullMemoryStore())
    result = await orch.handle("qualquer coisa")
    assert result.answer == FALLBACK_ANSWER
    assert result.sources == []


@pytest.mark.asyncio
async def test_fallback_when_tool_raises():
    orch = Orchestrator(
        tool=FakeTool(raise_exc=RuntimeError("boom")),
        llm_generate=_make_llm(),
        memory=NullMemoryStore(),
    )
    result = await orch.handle("qualquer")
    assert result.answer == FALLBACK_ANSWER
    assert result.sources == []


@pytest.mark.asyncio
async def test_fallback_when_llm_returns_fallback_marker():
    orch = Orchestrator(
        tool=FakeTool([SectionMatch("Falta de contexto", "...", 10)]),
        llm_generate=_make_llm(
            "Não encontrei informação suficiente na base para responder essa pergunta."
        ),
        memory=NullMemoryStore(),
    )
    result = await orch.handle("qualquer")
    assert result.answer == FALLBACK_ANSWER
    assert result.sources == []


@pytest.mark.asyncio
async def test_fallback_marker_detected_with_paraphrase():
    orch = Orchestrator(
        tool=FakeTool([SectionMatch("Composição", "...", 5)]),
        llm_generate=_make_llm(
            "Desculpe, nao encontrei informacao suficiente nessa base."
        ),
        memory=NullMemoryStore(),
    )
    result = await orch.handle("qualquer")
    assert result.answer == FALLBACK_ANSWER
    assert result.sources == []


@pytest.mark.asyncio
async def test_fallback_marker_detected_impersonal_phrasing():
    orch = Orchestrator(
        tool=FakeTool([SectionMatch("Composição", "...", 5)]),
        llm_generate=_make_llm(
            "Sobre esse tópico, não há informação suficiente na KB para responder."
        ),
        memory=NullMemoryStore(),
    )
    result = await orch.handle("qualquer")
    assert result.answer == FALLBACK_ANSWER
    assert result.sources == []


@pytest.mark.asyncio
async def test_fallback_marker_detected_first_person_phrasing():
    orch = Orchestrator(
        tool=FakeTool([SectionMatch("Composição", "...", 5)]),
        llm_generate=_make_llm(
            "Não tenho informação suficiente para dar uma resposta segura."
        ),
        memory=NullMemoryStore(),
    )
    result = await orch.handle("qualquer")
    assert result.answer == FALLBACK_ANSWER
    assert result.sources == []


@pytest.mark.asyncio
async def test_fallback_marker_does_not_match_unrelated_negation():
    orch = Orchestrator(
        tool=FakeTool([SectionMatch("Herança", "...", 5)]),
        llm_generate=_make_llm(
            "Use herança quando houver semelhança forte de contrato."
        ),
        memory=NullMemoryStore(),
    )
    result = await orch.handle("qualquer")
    assert result.answer != FALLBACK_ANSWER
    assert result.sources == [{"section": "Herança"}]


@pytest.mark.asyncio
async def test_fallback_when_llm_fails():
    orch = Orchestrator(
        tool=FakeTool([SectionMatch("Composição", "...", 5)]),
        llm_generate=_make_llm(raise_exc=LLMError("bad")),
        memory=NullMemoryStore(),
    )
    result = await orch.handle("qualquer")
    assert result.answer == FALLBACK_ANSWER
    assert result.sources == []


@pytest.mark.asyncio
async def test_fallback_when_llm_returns_empty():
    orch = Orchestrator(
        tool=FakeTool([SectionMatch("Composição", "...", 5)]),
        llm_generate=_make_llm(text="   "),
        memory=NullMemoryStore(),
    )
    result = await orch.handle("qualquer")
    assert result.answer == FALLBACK_ANSWER
    assert result.sources == []


@pytest.mark.asyncio
async def test_happy_path_filters_sources_by_citation_in_answer():
    orch = Orchestrator(
        tool=FakeTool([
            SectionMatch("Composição", "...", 10),
            SectionMatch("Herança", "...", 3),
        ]),
        llm_generate=_make_llm("Composição é..."),
        memory=NullMemoryStore(),
    )
    result = await orch.handle("O que é composição?")
    assert result.answer == "Composição é..."
    assert result.sources == [{"section": "Composição"}]


@pytest.mark.asyncio
async def test_happy_path_keeps_multiple_sources_when_both_cited():
    orch = Orchestrator(
        tool=FakeTool([
            SectionMatch("Endpoint de API", "...", 8),
            SectionMatch("Responsabilidade única", "...", 3),
        ]),
        llm_generate=_make_llm(
            "A regra de negócio deve ficar fora do endpoint, "
            "separada por responsabilidade."
        ),
        memory=NullMemoryStore(),
    )
    result = await orch.handle("Onde colocar regra de negócio?")
    assert result.sources == [
        {"section": "Endpoint de API"},
        {"section": "Responsabilidade única"},
    ]


@pytest.mark.asyncio
async def test_happy_path_keeps_top_when_nothing_cited():
    orch = Orchestrator(
        tool=FakeTool([
            SectionMatch("Composição", "...", 10),
            SectionMatch("Herança", "...", 3),
        ]),
        llm_generate=_make_llm("Resposta genérica sem citar títulos."),
        memory=NullMemoryStore(),
    )
    result = await orch.handle("pergunta")
    assert result.sources == [{"section": "Composição"}]


@pytest.mark.asyncio
async def test_memory_records_turns_when_session_provided():
    memory = InProcessMemoryStore(ttl_seconds=60, max_turns=6)
    orch = Orchestrator(
        tool=FakeTool([SectionMatch("Composição", "...", 5)]),
        llm_generate=_make_llm("ok"),
        memory=memory,
    )
    await orch.handle("pergunta 1", session_id="sess-1")
    history = memory.get_history("sess-1")
    assert [t.role for t in history] == ["user", "assistant"]
    assert history[0].content == "pergunta 1"


@pytest.mark.asyncio
async def test_memory_isolates_sessions():
    memory = InProcessMemoryStore(ttl_seconds=60, max_turns=6)
    orch = Orchestrator(
        tool=FakeTool([SectionMatch("Composição", "...", 5)]),
        llm_generate=_make_llm("ok"),
        memory=memory,
    )
    await orch.handle("msg A", session_id="A")
    await orch.handle("msg B", session_id="B")
    assert len(memory.get_history("A")) == 2
    assert len(memory.get_history("B")) == 2
    assert memory.get_history("A")[0].content == "msg A"
    assert memory.get_history("B")[0].content == "msg B"


class QuerySpyTool:
    """Tool de teste que só casa quando a query contém um keyword e grava as queries."""

    def __init__(self, keyword: str, match_section: str):
        self._keyword = keyword
        self._match_section = match_section
        self.queries_received: list[str] = []

    async def search(self, query: str):
        self.queries_received.append(query)
        if self._keyword.lower() in query.lower():
            return [SectionMatch(self._match_section, "conteudo", 10)]
        return []


@pytest.mark.asyncio
async def test_followup_uses_history_to_augment_search():
    memory = InProcessMemoryStore(ttl_seconds=60, max_turns=6)
    tool = QuerySpyTool(keyword="composicao", match_section="Composição")
    orch = Orchestrator(
        tool=tool,
        llm_generate=_make_llm("resposta"),
        memory=memory,
    )

    first = await orch.handle("O que é composicao?", session_id="sess-1")
    assert first.answer == "resposta"

    second = await orch.handle("Pode resumir em uma frase?", session_id="sess-1")
    assert second.answer == "resposta"
    assert second.sources == [{"section": "Composição"}]

    second_query = tool.queries_received[1]
    assert "resumir" in second_query.lower()
    assert "composicao" in second_query.lower()


@pytest.mark.asyncio
async def test_search_is_not_augmented_without_session():
    tool = QuerySpyTool(keyword="composicao", match_section="Composição")
    orch = Orchestrator(
        tool=tool,
        llm_generate=_make_llm("ok"),
        memory=NullMemoryStore(),
    )

    await orch.handle("O que é composicao?")
    await orch.handle("Pode resumir?")

    assert tool.queries_received[1] == "Pode resumir?"
