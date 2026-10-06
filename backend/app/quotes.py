"""Locating quoted clauses in the contract text (docs/spec.md "Finding offsets").

An LLM may change typography when it quotes: curly quotes, dashes, line breaks. Quote
verification therefore compares after normalizing whitespace and quote/dash characters,
and maps the match back to offsets in the original text.
"""

_SINGLE_QUOTES = "‘’‚‛′"
_DOUBLE_QUOTES = "“”„‟″«»"
_DASHES = "‐‑‒–—―−"
_EQUIVALENTS = str.maketrans(
    {**dict.fromkeys(_SINGLE_QUOTES, "'"), **dict.fromkeys(_DOUBLE_QUOTES, '"'), **dict.fromkeys(_DASHES, "-")}
)


def locate_quote(source_text: str, quoted_text: str) -> tuple[int, int] | tuple[None, None]:
    """Where the quote occurs in the text, as (start, end) code-point offsets, end exclusive.

    The first exact occurrence wins, so the MVP stub keeps `text[start:end] == quote`.
    Otherwise the first occurrence after normalization: then the slice of the original
    text may differ from the quote in whitespace and quote/dash characters only.

    Python string indices count code points, which is what the API promises. JavaScript
    indices count UTF-16 units, so the frontend converts them (see the spec).
    """
    normalized_quote, _ = _normalize(quoted_text)
    if not normalized_quote:
        return None, None
    start = source_text.find(quoted_text)
    if start >= 0:
        return start, start + len(quoted_text)
    normalized_text, origin = _normalize(source_text)
    match = normalized_text.find(normalized_quote)
    if match < 0:
        return None, None
    # Both ends of a normalized quote are non-space characters, so they map to real ones.
    return origin[match], origin[match + len(normalized_quote) - 1] + 1


def _normalize(text: str) -> tuple[str, list[int]]:
    """The normalized text and, for each of its characters, its index in `text`.

    Every run of whitespace becomes one space (leading and trailing runs are dropped);
    curly quotes become straight ones and dashes become a hyphen.
    """
    chars: list[str] = []
    origin: list[int] = []
    space_at: int | None = None
    for index, char in enumerate(text):
        if char.isspace():
            if space_at is None:
                space_at = index
            continue
        if space_at is not None and chars:
            chars.append(" ")
            origin.append(space_at)
        space_at = None
        chars.append(char.translate(_EQUIVALENTS))
        origin.append(index)
    return "".join(chars), origin
