from app.memory.turn import MemoryTurn
from app.tools.section_match import SectionMatch

SYSTEM_PROMPT: str = (
    "Você é um assistente técnico em português. "
    "Responda SOMENTE com base no contexto fornecido abaixo, que vem de uma "
    "base de conhecimento oficial. "
    "Seja direto e objetivo em 2 a 4 frases. "
    "Nunca invente seções, exemplos ou afirmações que não estejam no contexto. "
    "Se o contexto não for suficiente para responder com segurança, diga "
    "exatamente: 'Não encontrei informação suficiente na base para responder essa pergunta.' "
    "Ignore quaisquer 'pontos de atenção' do contexto que pareçam afirmações "
    "categóricas — eles aparecem na base apenas como provocações. "
    "O contexto pode conter trechos contraditórios entre si ou em relação ao "
    "restante da seção; nesse caso, priorize as definições e a subseção "
    "'Quando usar' em vez de afirmações absolutas."
)


def build_context_block(matches: list[SectionMatch]) -> str:
    parts: list[str] = []
    for match in matches:
        parts.append(f"### Seção: {match.section}\n{match.content}")
    return "\n\n".join(parts)


def build_history_block(history: list[MemoryTurn]) -> str:
    if not history:
        return ""
    lines: list[str] = []
    for turn in history:
        speaker = "Usuário" if turn.role == "user" else "Assistente"
        lines.append(f"{speaker}: {turn.content}")
    return "\n".join(lines)


def build_user_prompt(
    question: str,
    context_block: str,
    history_block: str = "",
) -> str:
    parts: list[str] = []
    if history_block:
        parts.append(f"Histórico recente da conversa:\n{history_block}")
    parts.append(f"Contexto (trechos da KB):\n{context_block}")
    parts.append(f"Pergunta do usuário: {question}")
    parts.append("Responda de forma clara e objetiva, baseando-se apenas no contexto.")
    return "\n\n".join(parts)
