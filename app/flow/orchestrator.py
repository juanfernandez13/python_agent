from collections.abc import Awaitable, Callable

from app.core.logging import get_logger
from app.flow.prompts import (
    SYSTEM_PROMPT,
    build_context_block,
    build_history_block,
    build_user_prompt,
)
from app.flow.result import FlowResult
from app.llm.error import LLMError
from app.llm.message import LLMMessage
from app.memory.protocol import MemoryStore
from app.memory.turn import MemoryTurn
from app.tools.knowledge_source import KnowledgeSource
from app.tools.section_match import SectionMatch
from app.utils.text import remove_accents, tokenize

logger = get_logger(__name__)

FALLBACK_ANSWER: str = (
    "Não encontrei informação suficiente na base para responder essa pergunta."
)

# Variações comuns que indicam que o LLM optou por fallback.
# Todas em minúsculas e sem acento — comparação é normalizada.
FALLBACK_MARKERS: tuple[str, ...] = tuple(
    remove_accents(phrase).lower()
    for phrase in (
        "não encontrei informação suficiente",
        "não tenho informação suficiente",
        "não há informação suficiente",
        "não foi possível encontrar informação",
        "informação insuficiente na base",
        "não consegui encontrar informação",
        "não disponho de informação suficiente",
        "não possuo informação suficiente",
        "informações insuficientes na base",
    )
)

META_SECTIONS: frozenset[str] = frozenset()


class Orchestrator:
    """Coordena o fluxo: tool -> (LLM | fallback) -> resposta.

    Regras de decisão:
    1. Tool consulta a KB. Se falha, vem vazia ou só traz seções marcadas
       como meta -> fallback canônico com sources vazio.
    2. Com matches úteis -> monta prompt com contexto + histórico curto +
       pergunta e chama o LLM.
    3. LLM falha ou devolve vazio -> fallback.
    4. Resposta contém marcador de fallback (qualquer paráfrase comum de
       "não encontrei informação suficiente") -> força resposta canônica
       com sources vazio.
    5. Resposta válida -> filtra sources mantendo apenas seções cujo
       primeiro token do título aparece na resposta (rede de segurança
       mantém o top-1 caso o filtro esvazie). Persiste turnos na memória
       quando há session_id.
    """

    def __init__(
        self,
        *,
        tool: KnowledgeSource,
        llm_generate: Callable[[list[LLMMessage]], Awaitable[str]],
        memory: MemoryStore,
    ) -> None:
        self._tool: KnowledgeSource = tool
        self._llm_generate: Callable[[list[LLMMessage]], Awaitable[str]] = llm_generate
        self._memory: MemoryStore = memory

    async def prewarm(self) -> None:
        await self._tool.prewarm()

    async def handle(
        self,
        message: str,
        session_id: str | None = None,
    ) -> FlowResult:
        history: list[MemoryTurn] = (
            self._memory.get_history(session_id) if session_id else []
        )
        search_query = self._augment_query(message, history)

        try:
            matches = await self._tool.search(search_query)
        except Exception as exc:
            logger.warning("tool_error err=%s", exc)
            return FlowResult(FALLBACK_ANSWER, [])

        useful = [m for m in matches if m.section not in META_SECTIONS]
        logger.info(
            "retrieval matches=%d useful=%d scores=%s augmented=%s",
            len(matches),
            len(useful),
            [m.score for m in useful],
            search_query != message,
        )
        if not useful:
            return FlowResult(FALLBACK_ANSWER, [])

        messages = self._build_messages(message, useful, history)

        try:
            raw_answer = await self._llm_generate(messages)
        except LLMError as exc:
            logger.warning("llm_error err=%s", exc)
            return FlowResult(FALLBACK_ANSWER, [])

        answer = (raw_answer or "").strip()
        if not answer:
            return FlowResult(FALLBACK_ANSWER, [])

        if self._is_fallback_answer(answer):
            return FlowResult(FALLBACK_ANSWER, [])

        if session_id:
            self._memory.add_turn(session_id, "user", message)
            self._memory.add_turn(session_id, "assistant", answer)

        cited = self._filter_cited(useful, answer)
        sources = [{"section": m.section} for m in cited]
        return FlowResult(answer=answer, sources=sources)

    @staticmethod
    def _is_fallback_answer(answer: str) -> bool:
        normalized: str = remove_accents(answer).lower()
        return any(marker in normalized for marker in FALLBACK_MARKERS)

    @staticmethod
    def _filter_cited(
        useful: list[SectionMatch],
        answer: str,
    ) -> list[SectionMatch]:
        answer_tokens: set[str] = set(tokenize(answer))
        cited: list[SectionMatch] = []
        for match in useful:
            title_tokens: list[str] = tokenize(match.section)
            if not title_tokens:
                continue
            if title_tokens[0] in answer_tokens:
                cited.append(match)
        if not cited and useful:
            cited = [useful[0]]
        return cited

    @staticmethod
    def _augment_query(message: str, history: list[MemoryTurn]) -> str:
        past_user_turns = [h.content for h in history if h.role == "user"]
        if not past_user_turns:
            return message
        return message + " " + " ".join(past_user_turns)

    @staticmethod
    def _build_messages(
        question: str,
        matches: list[SectionMatch],
        history: list[MemoryTurn],
    ) -> list[LLMMessage]:
        context = build_context_block(matches)
        history_block = build_history_block(history)
        user_prompt = build_user_prompt(question, context, history_block)
        return [
            LLMMessage(role="system", content=SYSTEM_PROMPT),
            LLMMessage(role="user", content=user_prompt),
        ]
