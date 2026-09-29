"""Build the Lovable prompt from the frontend-relevant parts of docs/spec.md.

The full spec is larger than Lovable's prompt limit, so this script keeps only
the sections the frontend needs and wraps them in the generation prompt.

Usage:
    python3 scripts/build_lovable_prompt.py                # print to stdout
    python3 scripts/build_lovable_prompt.py -o prompt.md   # write to a file
"""

import argparse
import re
import sys
from pathlib import Path

DEFAULT_SPEC = Path(__file__).resolve().parent.parent / "docs" / "spec.md"
MAX_CHARS = 50_000

PROMPT_HEADER = """\
Create a contract risk analysis web application called Anti-Scope Creep.
The product specification follows (frontend-relevant sections only). Implement
all five screens, the polling behavior, the 401 session-expiry handling, and the
legal disclaimer exactly as described.

Put every backend call in src/services/api.ts, following the section
"Frontend architecture constraints (for Lovable)": the ApiClient interface,
the data types from "API data shapes", a real HTTP implementation, and a
complete in-memory mock with the seed data, test triggers, and stub analyzer
fixture from the spec. Use the mock by default (VITE_USE_MOCK=true) so the whole
app runs without a backend. No fetch calls outside src/services/. Add tests.
"""

# (## section, ### subsections to keep or None for the whole section)
INCLUDED_SECTIONS = [
    ("Summary", None),
    ("Users and roles", None),
    ("User flows", None),
    ("Screens", None),
    ("API data shapes", None),
    ("API operations", None),
    ("Frontend architecture constraints (for Lovable)", None),
    ("Severity and analysis rules",
     {"Overall contract risk", "Email generation rule", "MVP stub analyzer"}),
    ("Contract status flow", {"Allowed states", "Transitions"}),
    ("Error handling", {"Error codes"}),
]
CATEGORY_SECTION = "Clause categories with examples"
CATEGORY_TABLE_START = "| Category ID |"


def split_by_heading(text: str, level: int) -> tuple[str, dict[str, str]]:
    """Split markdown into the text before the first heading and {title: body}."""
    marker = "#" * level + " "
    parts = re.split(rf"(?m)^(?={marker})", text)
    sections = {part.splitlines()[0][len(marker):].strip(): part for part in parts[1:]}
    return parts[0], sections


def keep_subsections(body: str, names: set[str]) -> str:
    """Keep the section intro plus only the named ### subsections."""
    intro, subsections = split_by_heading(body, 3)
    missing = names - subsections.keys()
    if missing:
        raise KeyError(f"subsections not found in spec: {sorted(missing)}")
    return intro + "".join(sub for title, sub in subsections.items() if title in names)


def category_table(body: str) -> str:
    """Keep only the heading and the category ID -> UI label table."""
    start = body.find(CATEGORY_TABLE_START)
    if start == -1:
        raise KeyError(f"category table not found in {CATEGORY_SECTION!r}")
    end = body.find("\n\n", start)
    return f"{body.splitlines()[0]}\n\n{body[start:end]}\n\n---\n\n"


def build_spec_excerpt(spec: str) -> str:
    """Return the frontend-relevant excerpt of the spec, in spec order."""
    preamble, sections = split_by_heading(spec, 2)
    wanted = [name for name, _ in INCLUDED_SECTIONS] + [CATEGORY_SECTION]
    missing = [name for name in wanted if name not in sections]
    if missing:
        raise KeyError(f"sections not found in spec: {missing}")
    rules = dict(INCLUDED_SECTIONS)
    chunks = [preamble]
    for title, body in sections.items():
        if title == CATEGORY_SECTION:
            chunks.append(category_table(body))
        elif title in rules:
            names = rules[title]
            chunks.append(body if names is None else keep_subsections(body, names))
    return "".join(chunks)


def build_prompt(spec: str) -> str:
    return f"{PROMPT_HEADER}\n<SPEC>\n{build_spec_excerpt(spec)}</SPEC>\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--spec", type=Path, default=DEFAULT_SPEC)
    parser.add_argument("-o", "--output", type=Path)
    args = parser.parse_args(argv)

    prompt = build_prompt(args.spec.read_text(encoding="utf-8"))
    if len(prompt) > MAX_CHARS:
        print(f"prompt is {len(prompt)} chars, over the {MAX_CHARS} limit", file=sys.stderr)
        return 1
    if args.output:
        args.output.write_text(prompt, encoding="utf-8")
        print(f"wrote {len(prompt)} chars to {args.output}", file=sys.stderr)
    else:
        sys.stdout.write(prompt)
    return 0


if __name__ == "__main__":
    sys.exit(main())
