"""Locating quoted clauses in the contract text (docs/spec.md "Finding offsets").

An LLM may change typography when it quotes: curly quotes, dashes, line breaks. Quote
verification therefore compares after normalizing whitespace and quote/dash characters,
and maps the match back to offsets in the original text.

It may also shorten a long clause with an ellipsis or drop a word ("each milestone" for
"each milestone amount"). Such quotes are matched too, but only when every word of the
quote is in the contract and the omitted words cannot change the meaning (numbers,
negations, "unlimited", "any"...). The caller stores the contract's own slice, so what
the user sees is always the contract's wording.
"""

import re
from difflib import SequenceMatcher

_ELLIPSIS = re.compile(r"\s*(?:\.\s*\.\s*\.|…)\s*")
_WORD = re.compile(r"\w+(?:['’]\w+)*")
_MIN_WORDS = 8  # shorter quotes must match after normalization only
_MIN_PART_WORDS = 4  # each part of a quote with an ellipsis
_MIN_RATIO = 0.9
_MAX_OMITTED = 2  # words of the contract the quote may leave out
_NUMBER_WORDS = (
    "zero one two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen sixteen "
    "seventeen eighteen nineteen twenty thirty forty fifty sixty seventy eighty ninety hundred thousand "
    "million half double twice once"
)
_MEANING_WORDS = "not no never without unless except nor neither unlimited all any each every none only sole solely exclusive non"
_CRITICAL = frozenset(_NUMBER_WORDS.split()) | frozenset(_MEANING_WORDS.split())

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
    Otherwise a quote shortened with an ellipsis, then a quote that leaves out a few
    words (see the module docstring).

    Python string indices count code points, which is what the API promises. JavaScript
    indices count UTF-16 units, so the frontend converts them (see the spec).
    """
    found = _locate_normalized(source_text, quoted_text)
    if found[0] is not None or not _normalize(quoted_text)[0]:
        return found
    for tolerant in (_locate_with_ellipsis, _locate_by_words):
        span = tolerant(source_text, quoted_text)
        if span is not None:
            return span
    return None, None


def _locate_normalized(source_text: str, quoted_text: str) -> tuple[int, int] | tuple[None, None]:
    """The first exact occurrence, else the first one after normalization."""
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


def _locate_with_ellipsis(source_text: str, quoted_text: str) -> tuple[int, int] | None:
    """From the first part to the last one, when every part occurs in order and close together."""
    parts = [part for part in _ELLIPSIS.split(quoted_text) if part.strip()]
    if len(parts) < 2 or any(len(_WORD.findall(part)) < _MIN_PART_WORDS for part in parts):
        return None
    first, position = None, 0
    for part in parts:
        start, end = _locate_normalized(source_text[position:], part)
        if start is None:
            return None
        first = position + start if first is None else first
        position += end
    # The omitted text may be longer than the quote, but not a different section of the contract.
    if position - first > 3 * len(quoted_text) + 2000:
        return None
    return first, position


def _locate_by_words(source_text: str, quoted_text: str) -> tuple[int, int] | None:
    """The window of words most similar to the quote, if it only adds a few harmless words to it."""
    quote = [word.lower() for word in _WORD.findall(quoted_text)]
    if len(quote) < _MIN_WORDS:
        return None
    spans = [(m.group().lower(), m.start(), m.end()) for m in _WORD.finditer(source_text)]
    words = [word for word, _, _ in spans]
    anchor = SequenceMatcher(None, words, quote, autojunk=False).find_longest_match(0, len(words), 0, len(quote))
    if anchor.size < 3:
        return None
    best = _best_window(words, quote, anchor.a - anchor.b)
    if best is None or not _only_harmless_omissions(words[best[0] : best[1]], quote):
        return None
    return spans[best[0]][1], spans[best[1] - 1][2]


def _best_window(words: list[str], quote: list[str], offset: int) -> tuple[int, int] | None:
    """The window near `offset` with the highest similarity to the quote, if at least _MIN_RATIO."""
    slack = max(2, len(quote) // 10)
    best_ratio, best = _MIN_RATIO, None
    for start in range(max(0, offset - slack), min(len(words), offset + slack + 1)):
        for length in range(len(quote) - slack, len(quote) + slack + 1):
            end = start + length
            if end > len(words):
                break
            ratio = SequenceMatcher(None, words[start:end], quote, autojunk=False).ratio()
            if ratio > best_ratio or (best is None and ratio == best_ratio):
                best_ratio, best = ratio, (start, end)
    return best


def _only_harmless_omissions(window: list[str], quote: list[str]) -> bool:
    """Every quoted word occurs in the window in order, and the few omitted ones cannot change the meaning.

    A word the model added or replaced is never accepted: "handled as part of the Services"
    must not match "handled as new Services". Omitted numbers and negations are not either.
    """
    omitted: list[str] = []
    for tag, i1, i2, _, _ in SequenceMatcher(None, window, quote, autojunk=False).get_opcodes():
        if tag == "delete":
            omitted += window[i1:i2]
        elif tag != "equal":
            return False
    return len(omitted) <= _MAX_OMITTED and not any(
        word in _CRITICAL or any(char.isdigit() for char in word) for word in omitted
    )


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
