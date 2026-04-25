from app.utils import compact_whitespace, remove_accents, tokenize


def test_remove_accents():
    assert remove_accents("Composição e herança") == "Composicao e heranca"


def test_tokenize_removes_stopwords_and_accents():
    tokens = tokenize("O que é composição?")
    assert "composicao" in tokens
    assert "que" not in tokens


def test_tokenize_filters_short_tokens():
    assert tokenize("a b ab abc") == ["abc"]


def test_compact_whitespace_collapses_spaces_and_trims():
    assert compact_whitespace("  a  \n b\tc  ") == "a b c"
