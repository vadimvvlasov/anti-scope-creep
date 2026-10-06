import pytest

from app.chunking import DEFAULT_MAX_CHARS, chunk_text


def paragraph(n: int, length: int) -> str:
    sentence = f"Clause {n} says something about the work. "
    return (sentence * (length // len(sentence) + 1))[:length].rstrip()


def test_a_short_text_is_one_chunk():
    assert chunk_text("First paragraph.\n\nSecond paragraph.") == ["First paragraph.\n\nSecond paragraph."]


def test_a_30000_character_contract_fits_in_three_chunks_on_paragraph_boundaries():
    paragraphs = [paragraph(n, 1_500) for n in range(20)]
    chunks = chunk_text("\n\n".join(paragraphs))

    assert len(chunks) == 3
    assert all(len(c) <= DEFAULT_MAX_CHARS for c in chunks)
    assert [p for c in chunks for p in c.split("\n\n")] == paragraphs  # nothing lost, order kept


def test_an_oversized_paragraph_is_split_on_sentence_ends():
    text = " ".join(f"Sentence number {n} is here." for n in range(100))
    chunks = chunk_text(text, max_chars=300)

    assert all(len(c) <= 300 for c in chunks)
    assert all(c.endswith(".") for c in chunks)
    assert " ".join(chunks) == text


def test_a_sentence_longer_than_the_limit_is_cut_at_whitespace_or_hard():
    assert chunk_text("word " * 30, max_chars=22) == ["word word word word"] * 7 + ["word word"]
    assert chunk_text("x" * 25, max_chars=10) == ["x" * 10, "x" * 10, "x" * 5]


def test_blank_lines_with_spaces_separate_paragraphs_and_empty_text_has_no_chunks():
    assert chunk_text("A.\n  \nB.", max_chars=3) == ["A.", "B."]
    assert chunk_text("  \n\n ") == []


def test_max_chars_must_be_positive():
    with pytest.raises(ValueError):
        chunk_text("text", max_chars=0)
