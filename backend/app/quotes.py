"""Locating quoted clauses in the contract text (docs/spec.md "Finding offsets")."""


def locate_quote(source_text: str, quoted_text: str) -> tuple[int, int] | tuple[None, None]:
    """First exact occurrence of the quote as (start, end) code-point offsets, end exclusive.

    Python string indices count code points, which is what the API promises. JavaScript
    indices count UTF-16 units, so the frontend converts them (see the spec).
    """
    start = source_text.find(quoted_text)
    if start < 0:
        return None, None
    return start, start + len(quoted_text)
