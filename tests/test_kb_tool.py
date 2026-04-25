import pytest

from app.tools import KnowledgeTool

SAMPLE_KB = """# Base

## Composição

### Definição
Composição é quando uma função/classe utiliza outra instância.

### Quando usar
Use para reduzir acoplamento.

## Herança

### Definição
Herança permite compartilhar atributos e comportamentos.

## Tool de conhecimento

### Definição
Tool consulta a base markdown.
"""


def _tool_with_cached_markdown(markdown: str) -> KnowledgeTool:
    tool = KnowledgeTool(kb_url="http://unused", cache_ttl=999_999)
    tool._cached_markdown = markdown
    import time as _t
    tool._cached_at = _t.monotonic()
    return tool


@pytest.mark.asyncio
async def test_search_finds_composicao():
    tool = _tool_with_cached_markdown(SAMPLE_KB)
    matches = await tool.search("O que é composição?")
    assert matches
    assert matches[0].section == "Composição"


@pytest.mark.asyncio
async def test_search_returns_empty_for_unrelated_query():
    tool = _tool_with_cached_markdown(SAMPLE_KB)
    matches = await tool.search("pizza margherita")
    assert matches == []


@pytest.mark.asyncio
async def test_title_weight_promotes_title_match():
    tool = _tool_with_cached_markdown(SAMPLE_KB)
    matches = await tool.search("tool conhecimento")
    assert matches[0].section == "Tool de conhecimento"


def test_parse_sections_handles_multiple_headings():
    tool = KnowledgeTool(kb_url="http://unused")
    sections = tool._parse_sections(SAMPLE_KB)
    titles = [s[0] for s in sections]
    assert titles == ["Composição", "Herança", "Tool de conhecimento"]
