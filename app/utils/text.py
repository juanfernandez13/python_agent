import re
import unicodedata

STOPWORDS_PT = frozenset({
    "a", "o", "os", "as", "de", "da", "do", "das", "dos",
    "e", "em", "no", "na", "nos", "nas",
    "um", "uma", "uns", "umas",
    "para", "por", "com", "sem", "sobre",
    "que", "qual", "quais", "como", "quando", "onde",
    "porque", "porque", "porquê",
    "é", "ser", "sao", "são", "era", "foi",
    "ou", "se", "ao", "aos", "à", "às",
    "isso", "isto", "aquilo", "meu", "sua", "seu",
    "ela", "ele", "eles", "elas",
})

MIN_TOKEN_LEN = 3


def remove_accents(text: str) -> str:
    normalized = unicodedata.normalize("NFD", text)
    return "".join(ch for ch in normalized if unicodedata.category(ch) != "Mn")


def tokenize(text: str) -> list[str]:
    lowered = remove_accents(text.lower())
    cleaned = re.sub(r"[^a-z0-9\s]", " ", lowered)
    tokens = (t for t in cleaned.split() if t)
    return [t for t in tokens if len(t) >= MIN_TOKEN_LEN and t not in STOPWORDS_PT]


def compact_whitespace(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()
