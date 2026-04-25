import time

import httpx

from app.core.logging import get_logger
from app.tools.section_match import SectionMatch
from app.utils.text import compact_whitespace, tokenize

logger = get_logger(__name__)


class KnowledgeTool:
    """Busca seções relevantes da KB em Markdown via HTTP.

    Faz cache em memória do Markdown com TTL para evitar baixar a cada request.
    Ranqueia seções por sobreposição de tokens, com peso 2x no título.
    """

    def __init__(
        self,
        kb_url: str,
        *,
        top_k: int = 3,
        min_score: int = 2,
        http_timeout: int = 15,
        cache_ttl: int = 60,
    ) -> None:
        self._kb_url: str = kb_url
        self._top_k: int = top_k
        self._min_score: int = min_score
        self._http_timeout: int = http_timeout
        self._cache_ttl: int = cache_ttl
        self._cached_markdown: str | None = None
        self._cached_at: float = 0.0

    async def search(self, query: str) -> list[SectionMatch]:
        query_tokens = set(tokenize(query))
        if not query_tokens:
            return []

        markdown = await self._fetch_markdown()
        sections = self._parse_sections(markdown)
        return self._rank(sections, query_tokens)

    async def prewarm(self) -> None:
        try:
            await self._fetch_markdown(force=True)
        except Exception as exc:
            logger.warning("kb_prewarm_failed url=%s err=%s", self._kb_url, exc)

    async def _fetch_markdown(self, *, force: bool = False) -> str:
        now = time.monotonic()
        fresh = (
            self._cached_markdown is not None
            and (now - self._cached_at) < self._cache_ttl
        )
        if fresh and not force:
            return self._cached_markdown  # type: ignore[return-value]

        async with httpx.AsyncClient(timeout=self._http_timeout) as client:
            response = await client.get(self._kb_url)
            response.raise_for_status()
            self._cached_markdown = response.text
            self._cached_at = now
            logger.info("kb_fetched bytes=%d", len(self._cached_markdown))
            return self._cached_markdown

    @staticmethod
    def _parse_sections(markdown: str) -> list[tuple[str, str]]:
        sections: list[tuple[str, str]] = []
        current_title: str | None = None
        buffer: list[str] = []

        for line in markdown.splitlines():
            if line.startswith("## "):
                if current_title is not None:
                    sections.append((current_title, "\n".join(buffer).strip()))
                current_title = line[3:].strip()
                buffer = []
                continue
            if current_title is not None:
                buffer.append(line)

        if current_title is not None:
            sections.append((current_title, "\n".join(buffer).strip()))
        return sections

    def _rank(
        self,
        sections: list[tuple[str, str]],
        query_tokens: set[str],
    ) -> list[SectionMatch]:
        matches: list[SectionMatch] = []
        for title, content in sections:
            title_tokens = set(tokenize(title))
            content_tokens = set(tokenize(content))
            score = (
                len(query_tokens & content_tokens)
                + 2 * len(query_tokens & title_tokens)
            )
            if score < self._min_score:
                continue
            matches.append(
                SectionMatch(
                    section=title,
                    content=compact_whitespace(content),
                    score=score,
                )
            )

        matches.sort(key=lambda m: m.score, reverse=True)
        return matches[: self._top_k]
