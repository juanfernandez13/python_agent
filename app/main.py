from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api import router as messages_router
from app.core import Settings, configure_logging, get_logger, get_settings
from app.flow import Orchestrator
from app.llm import LLMClient
from app.memory import (
    InProcessMemoryStore,
    MemoryStore,
    NullMemoryStore,
    RedisMemoryStore,
)
from app.tools import KnowledgeTool

logger = get_logger(__name__)


def _build_memory(settings: Settings) -> MemoryStore:
    if not settings.MEMORY_ENABLED:
        logger.info("memory_backend=null")
        return NullMemoryStore()

    redis_url = settings.MEMORY_STORE.strip()
    if redis_url:
        store = RedisMemoryStore(
            url=redis_url,
            ttl_seconds=settings.MEMORY_TTL_SECONDS,
            max_turns=settings.MEMORY_MAX_TURNS,
        )
        if store.ping():
            logger.info("memory_backend=redis url=%s", redis_url)
            return store
        logger.warning(
            "memory_backend=redis_unavailable_falling_back_to_in_process url=%s",
            redis_url,
        )

    logger.info("memory_backend=in_process")
    return InProcessMemoryStore(
        ttl_seconds=settings.MEMORY_TTL_SECONDS,
        max_turns=settings.MEMORY_MAX_TURNS,
    )


def _build_orchestrator(settings: Settings) -> Orchestrator:
    tool = KnowledgeTool(
        kb_url=str(settings.KB_URL),
        top_k=settings.CONTEXT_TOP_K,
        min_score=settings.CONTEXT_MIN_SCORE,
        http_timeout=settings.KB_TIMEOUT_SECONDS,
        cache_ttl=settings.KB_CACHE_TTL_SECONDS,
    )
    llm = LLMClient(
        provider=settings.LLM_PROVIDER,
        model=settings.LLM_MODEL,
        base_url=settings.LLM_BASE_URL,
        api_key=settings.LLM_API_KEY,
        temperature=settings.LLM_TEMPERATURE,
        max_tokens=settings.LLM_MAX_TOKENS,
        timeout=settings.LLM_TIMEOUT_SECONDS,
    )
    memory = _build_memory(settings)
    return Orchestrator(tool=tool, llm_generate=llm.generate, memory=memory)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    configure_logging(settings.LOG_LEVEL)
    logger.info(
        "startup provider=%s model=%s kb_ttl=%ds memory=%s",
        settings.LLM_PROVIDER,
        settings.LLM_MODEL,
        settings.KB_CACHE_TTL_SECONDS,
        "on" if settings.MEMORY_ENABLED else "off",
    )

    orchestrator = _build_orchestrator(settings)
    app.state.settings = settings
    app.state.orchestrator = orchestrator

    # Pré-aquece o cache da KB para a primeira request não pagar o custo.
    await orchestrator.prewarm()

    yield
    logger.info("shutdown")


async def health() -> dict[str, str]:
    return {"status": "ok"}


def create_app() -> FastAPI:
    app = FastAPI(
        title="Python Agent Challenge",
        version="1.0.0",
        lifespan=lifespan,
    )
    app.include_router(messages_router)
    app.add_api_route("/health", health, methods=["GET"])
    return app


app = create_app()
