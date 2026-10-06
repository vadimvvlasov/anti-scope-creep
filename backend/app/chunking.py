"""Splitting a contract into chunks that fit one LLM request (docs/architecture.md, section 4).

A 30,000-character contract plus the prompt and the answer exceeds the free-tier limit of
8,000 tokens per minute, so it is analyzed in chunks of about 12,000 characters, cut on
paragraph boundaries. Quotes are verified against the full source text afterwards, so a
chunk does not need to reproduce the original whitespace between paragraphs.
"""

import re

DEFAULT_MAX_CHARS = 12_000

_PARAGRAPH_BREAK = re.compile(r"\n[ \t]*\n")
_SENTENCE_END = re.compile(r"(?<=[.!?;:])\s+")


def chunk_text(text: str, max_chars: int = DEFAULT_MAX_CHARS) -> list[str]:
    """Chunks of at most `max_chars` characters, in order; paragraphs are kept whole if they fit.

    A paragraph longer than `max_chars` is split on sentence ends, and a sentence longer
    than that at the last whitespace before the limit.
    """
    if max_chars < 1:
        raise ValueError("max_chars must be positive")
    pieces = [p.strip() for p in _PARAGRAPH_BREAK.split(text) if p.strip()]
    units = [unit for piece in pieces for unit in _fit(piece, max_chars)]
    chunks: list[str] = []
    for unit in units:
        if chunks and len(chunks[-1]) + 2 + len(unit) <= max_chars:
            chunks[-1] = f"{chunks[-1]}\n\n{unit}"
        else:
            chunks.append(unit)
    return chunks


def _fit(paragraph: str, max_chars: int) -> list[str]:
    """The paragraph itself, or sentence groups and hard splits that each fit."""
    if len(paragraph) <= max_chars:
        return [paragraph]
    parts: list[str] = []
    for sentence in _SENTENCE_END.split(paragraph):
        pieces = [sentence] if len(sentence) <= max_chars else _hard_split(sentence, max_chars)
        for piece in pieces:
            if parts and len(parts[-1]) + 1 + len(piece) <= max_chars:
                parts[-1] = f"{parts[-1]} {piece}"
            else:
                parts.append(piece)
    return parts


def _hard_split(sentence: str, max_chars: int) -> list[str]:
    """Cut at the last whitespace before the limit, or at the limit if there is none."""
    parts = []
    while len(sentence) > max_chars:
        cut = sentence.rfind(" ", 0, max_chars + 1)
        cut = cut if cut > 0 else max_chars
        parts.append(sentence[:cut].rstrip())
        sentence = sentence[cut:].lstrip()
    if sentence:
        parts.append(sentence)
    return parts
