from typing import Protocol

from app.tools.section_match import SectionMatch


class KnowledgeSource(Protocol):
    async def search(self, query: str) -> list[SectionMatch]: ...
    async def prewarm(self) -> None: ...
