"""Rule-based pseudonymization before text goes to an LLM provider.

docs/spec.md "Pseudonymization rules": party and signatory names, email addresses, phone
numbers, URLs, bank account / IBAN numbers, tax or company registration IDs and labelled
street addresses become
typed, numbered placeholders such as [PARTY_A], [PERSON_1], [EMAIL_1]. Amounts, payment
periods, durations, dates, percentages and caps stay: the severity matrix depends on them.

Detection is best-effort: names are taken from party definitions, the preamble and the
signature block, other values from conservative patterns. A missed value is sent as is.

The mapping lives only in memory for one analysis run. It is never logged, and its repr
does not show the original values.
"""

import re
from dataclasses import dataclass, field

# Words that name a role, not a party: "the Client" is not a name to hide.
_ROLES = (
    "Agency", "Client", "Company", "Consultant", "Contractor", "Customer", "Designer", "Developer",
    "Freelancer", "Licensee", "Licensor", "Provider", "Studio", "Supplier", "Vendor",
)
_ROLE_WORDS = {r.lower() for r in _ROLES} | {
    "agreement", "parties", "party", "services", "service", "the", "this",
}
# An address in the preamble is not a party: "100 Montgomery Street, Suite 1800".
_ADDRESS_WORDS = {
    "avenue", "ave", "boulevard", "blvd", "drive", "floor", "highway", "lane", "road", "square",
    "street", "st", "suite", "way",
}
_NAME = r"[A-Z][\w&.'-]*(?:[ \t]+(?:[A-Z][\w&.'-]*|&|of|and|de|van|von|der|z|o\.o\.))*"
_ROLE = "(?:" + "|".join(_ROLES) + ")"

# 'Acme Corp. ("Client")', 'Jane Doe (the “Contractor”)'
_DEFINED_PARTY = re.compile(
    rf"({_NAME})(?:\s*,[^()\n]{{0,200}}?)?\s*\(\s*(?:the\s+)?[\"“']{_ROLE}[\"”']\s*\)"
)
# 'between Acme Corp. and Jane Doe' in the preamble
_BETWEEN = re.compile(rf"\bbetween\s+({_NAME})(?=\s*[,(]|\s+and\b).{{0,200}}?\band\s+({_NAME})(?=\s*[,(.])", re.S)
# 'Apex Inc., a Delaware corporation', '1. Jane Doe, an individual' (numbered party lists too)
_INTRODUCED_PARTY = re.compile(
    rf"({_NAME}),\s+an?\s+(?:[\w-]+\s+){{0,6}}?"
    r"(?:corporation|company|enterprise|partnership|business|entity|organization|individual)\b"
)
# 'By: Jane Doe', 'Name: John Smith' in the signature block
_SIGNATORY = re.compile(rf"^[ \t]*(?:By|Name|Signed|Signature)[ \t]*:[ \t]*({_NAME})[ \t]*(?:,[^\n]*)?$", re.M)

_PATTERNS = (
    ("EMAIL", re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")),
    ("URL", re.compile(r"\b(?:https?://|www\.)[^\s<>\"')\]]+[^\s<>\"')\].,;:]")),
    ("IBAN", re.compile(r"\b[A-Z]{2}\d{2}(?: ?[A-Z0-9]{4}){2,7}(?: ?[A-Z0-9]{1,4})?\b")),
    # Labelled values only, so amounts and dates never match.
    ("ACCOUNT", re.compile(r"(?i:account\s+(?:number|no\.?|#))\s*:?\s*([A-Z0-9][A-Z0-9 -]{4,30}[A-Z0-9])")),
    # The first identifier after an ID keyword on the same line: 'Registration No: US-DE-9876543',
    # 'Tax ID/EIN: EIN 12-3456789', 'ID/Passport N-9876543'. Dates are not identifiers.
    ("ID", re.compile(
        r"(?i:\b(?:registration|tax|ein|tin|vat|inn|passport|identification|crn|company\s+no\.?))\b"
        r"[^\n\d]{0,40}?"
        r"\b((?:[A-Za-z]{1,5}-){0,3}[A-Z]{0,4} ?(?!\d{4}-\d{2}-\d{2}\b)\d[\dA-Za-z.-]{4,24})\b"
    )),
    # A street address after a label, up to a bracket, a semicolon, the line or sentence end:
    # 'Address: 1 Main St, Springfield', 'located at 25 Bank Street, London E14 5JP ("Client")'.
    ("ADDRESS", re.compile(
        r"(?i:\b(?:address|located at|residing at|resident at|(?:principal|registered)\s+"
        r"(?:place of business|(?:corporate\s+)?offices?)\s+(?:at|is))\b)\s*:?\s*"
        r"([0-9A-Z][^()\n;\[\]]{3,150}?)(?=\s*\(|;|\n|$|,\s*(?:hereinafter|represented)\b|\.(?:\s|$))"
    )),
    ("PHONE", re.compile(
        r"(?:\+\d[\d ().-]{6,18}\d)|(?i:(?:phone|tel\.?|telephone|mobile)\s*:?\s*)(\(?\d[\d ().-]{5,18}\d)"
    )),
)
_PLACEHOLDER = re.compile(r"\[([A-Z]+_[A-Z0-9]+)\]")
_BARE_PLACEHOLDER = re.compile(
    r"(?<!\[)\b((?:PARTY|PERSON|EMAIL|URL|IBAN|ACCOUNT|ID|PHONE|ADDRESS)_[A-Z0-9]+)\b(?!\])"
)


@dataclass
class PlaceholderMap:
    """Placeholder <-> original value for one analysis run. Memory only."""

    _values: dict[str, str] = field(default_factory=dict)
    _placeholders: dict[str, str] = field(default_factory=dict)
    _counts: dict[str, int] = field(default_factory=dict)

    def placeholder_for(self, kind: str, value: str) -> str:
        if value in self._placeholders:
            return self._placeholders[value]
        number = self._counts.get(kind, 0) + 1
        self._counts[kind] = number
        suffix = _party_letter(number) if kind == "PARTY" else str(number)
        placeholder = f"[{kind}_{suffix}]"
        self._placeholders[value] = placeholder
        self._values[placeholder] = value
        return placeholder

    def value_of(self, placeholder: str) -> str | None:
        return self._values.get(placeholder)

    def placeholder_of(self, value: str) -> str | None:
        return self._placeholders.get(value)

    def values(self) -> list[str]:
        """Original values, longest first, so a longer name is replaced before its prefix."""
        return sorted(self._placeholders, key=len, reverse=True)

    def __len__(self) -> int:
        return len(self._values)

    def __repr__(self) -> str:
        return f"PlaceholderMap({len(self)} placeholders)"


def pseudonymize(text: str) -> tuple[str, PlaceholderMap]:
    """The text with detected values replaced by placeholders, and the mapping."""
    mapping = PlaceholderMap()
    for kind, name in _names(text):
        mapping.placeholder_for(kind, name)
    text = _replace_known(text, mapping)
    for kind, pattern in _PATTERNS:
        text = pattern.sub(lambda m, kind=kind: _replace_match(m, kind, mapping), text)
    # A value found once (e.g. a labelled registration ID) is hidden everywhere it repeats.
    return _replace_known(text, mapping), mapping


def _replace_known(text: str, mapping: PlaceholderMap) -> str:
    values = mapping.values()
    if not values:
        return text
    pattern = re.compile("|".join(rf"(?<!\w){re.escape(v)}(?!\w)" for v in values))
    return pattern.sub(lambda m: mapping.placeholder_of(m.group(0)) or m.group(0), text)


def restore(text: str, mapping: PlaceholderMap) -> tuple[str, list[str]]:
    """The text with known placeholders restored, and the placeholders that are unknown.

    A placeholder the mapping does not know, or a known one without its brackets, cannot
    be restored reliably; the caller drops the finding (docs/spec.md "Quote verification").
    """
    unknown: list[str] = []

    def _restore(match: re.Match[str]) -> str:
        value = mapping.value_of(match.group(0))
        if value is None:
            unknown.append(match.group(0))
            return match.group(0)
        return value

    restored = _PLACEHOLDER.sub(_restore, text)
    unknown.extend(m.group(1) for m in _BARE_PLACEHOLDER.finditer(text))
    return restored, unknown


def _names(text: str) -> list[tuple[str, str]]:
    """(kind, name) of parties first, then signatories, in order of appearance."""
    parties = [m.group(1) for m in _DEFINED_PARTY.finditer(text)]
    parties += [m.group(1) for m in _INTRODUCED_PARTY.finditer(text)]
    between = _BETWEEN.search(text)
    if between:
        parties += [between.group(1), between.group(2)]
    found = [("PARTY", _clean(name)) for name in parties]
    found += [("PERSON", _clean(m.group(1))) for m in _SIGNATORY.finditer(text)]
    names = {name for _, name in found}
    seen: set[str] = set()
    result = []
    for kind, name in found:
        # A cut-off variant ("Acme Sp" next to "Acme Sp. z o.o.") is part of the longer name.
        truncated = any(other != name and other.startswith(name) for other in names)
        if name and name not in seen and not truncated and not _is_role(name) and not _is_address(name):
            seen.add(name)
            result.append((kind, name))
    return result


def _replace_match(match: re.Match[str], kind: str, mapping: PlaceholderMap) -> str:
    """Replace the value part of a match: the labelled group if there is one, else all."""
    group = next((i for i in range(1, (match.re.groups or 0) + 1) if match.group(i)), 0)
    value = match.group(group)
    if _PLACEHOLDER.fullmatch(value) or (kind == "ADDRESS" and not re.search(r"\d", value)):
        return match.group(0)
    start, end = match.start(group) - match.start(), match.end(group) - match.start()
    whole = match.group(0)
    return whole[:start] + mapping.placeholder_for(kind, value) + whole[end:]


def _clean(name: str) -> str:
    """Drop a trailing comma or a sentence period that is not part of an abbreviation."""
    name = name.strip().rstrip(",")
    if name.endswith(".") and not re.search(r"\b(?:Inc|Corp|Ltd|Co|LLC|L\.L\.C|S\.A|GmbH|B\.V|N\.V|o\.o)\.$", name):
        name = name[:-1]
    return name.strip()


def _is_role(name: str) -> bool:
    return all(word.lower().strip(".,") in _ROLE_WORDS for word in name.split())


def _is_address(name: str) -> bool:
    return any(word.lower().strip(".,") in _ADDRESS_WORDS for word in name.split())


def _party_letter(number: int) -> str:
    """A, B, ..., Z, then 27, 28, ... (contracts rarely have more than two parties)."""
    return chr(ord("A") + number - 1) if number <= 26 else str(number)
