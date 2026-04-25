from app.flow.prompts import (
    build_context_block,
    build_history_block,
    build_user_prompt,
)
from app.memory.turn import MemoryTurn
from app.tools import SectionMatch


def test_build_context_block_formats_each_section():
    matches: list[SectionMatch] = [
        SectionMatch("Composição", "conteudo da composicao", 5),
        SectionMatch("Herança", "conteudo da heranca", 3),
    ]
    block: str = build_context_block(matches)
    assert "### Seção: Composição" in block
    assert "conteudo da composicao" in block
    assert "### Seção: Herança" in block
    assert "conteudo da heranca" in block


def test_build_history_block_returns_empty_when_no_history():
    assert build_history_block([]) == ""


def test_build_history_block_labels_speakers():
    history: list[MemoryTurn] = [
        MemoryTurn(role="user", content="pergunta 1", timestamp=1.0),
        MemoryTurn(role="assistant", content="resposta 1", timestamp=2.0),
    ]
    block: str = build_history_block(history)
    assert "Usuário: pergunta 1" in block
    assert "Assistente: resposta 1" in block


def test_build_user_prompt_omits_history_when_empty():
    prompt: str = build_user_prompt("o que é X?", "ctx", "")
    assert "Histórico recente" not in prompt
    assert "Contexto (trechos da KB):\nctx" in prompt
    assert "Pergunta do usuário: o que é X?" in prompt


def test_build_user_prompt_includes_history_when_present():
    prompt: str = build_user_prompt("resuma", "ctx", "Usuário: oi\nAssistente: olá")
    assert "Histórico recente da conversa:" in prompt
    assert "Usuário: oi" in prompt
    assert "Assistente: olá" in prompt
    assert "Pergunta do usuário: resuma" in prompt
