"""Tests for build_lovable_prompt. Run: python3 -m unittest discover scripts"""

import unittest

from build_lovable_prompt import (
    DEFAULT_SPEC,
    MAX_CHARS,
    build_prompt,
    build_spec_excerpt,
)

SAMPLE_SPEC = """\
# Title

## Summary

Intro text.

## Data model

Backend only.

## Screens

Screen list.

## API data shapes

Types.

## API operations

Paths.

## Frontend architecture constraints (for Lovable)

Mock rules.

## Users and roles

Roles.

## User flows

Flows.

## Clause categories with examples

Detection rules.

| Category ID | UI label |
|---|---|
| `scope_creep` | Scope creep |

### 1. Scope creep

Long detection text.

## Severity and analysis rules

### Deterministic severity matrix

Matrix.

### Overall contract risk

Derived risk.

### Email generation rule

Email rule.

### MVP stub analyzer

Fixture.

## Contract status flow

### Allowed states

States.

### Transitions

Arrows.

### Stale analysis rule

Backend detail.

## Error handling

Envelope.

### Error codes

Codes.

### Validation and normalization

Backend checks.

## Later phases

Future work.
"""


class BuildSpecExcerptTest(unittest.TestCase):
    def setUp(self):
        self.excerpt = build_spec_excerpt(SAMPLE_SPEC)

    def test_keeps_frontend_sections_and_subsections(self):
        for text in ("Intro text.", "Screen list.", "Mock rules.", "Derived risk.",
                     "Fixture.", "Arrows.", "Envelope.", "Codes.", "`scope_creep`"):
            self.assertIn(text, self.excerpt)

    def test_drops_backend_only_content(self):
        for text in ("Backend only.", "Future work.", "Matrix.", "Backend detail.",
                     "Backend checks.", "Detection rules.", "Long detection text."):
            self.assertNotIn(text, self.excerpt)

    def test_preserves_spec_order(self):
        self.assertLess(self.excerpt.index("Screen list."), self.excerpt.index("Roles."))

    def test_missing_section_raises(self):
        with self.assertRaises(KeyError):
            build_spec_excerpt(SAMPLE_SPEC.replace("## Screens", "## Views"))

    def test_missing_subsection_raises(self):
        with self.assertRaises(KeyError):
            build_spec_excerpt(SAMPLE_SPEC.replace("### Error codes", "### Codes"))


class BuildPromptTest(unittest.TestCase):
    def test_wraps_excerpt_in_spec_tags(self):
        prompt = build_prompt(SAMPLE_SPEC)
        self.assertTrue(prompt.startswith("Create a contract risk analysis"))
        self.assertIn("<SPEC>\n# Title", prompt)
        self.assertTrue(prompt.endswith("</SPEC>\n"))

    def test_real_spec_fits_lovable_limit(self):
        prompt = build_prompt(DEFAULT_SPEC.read_text(encoding="utf-8"))
        self.assertLess(len(prompt), MAX_CHARS)
        self.assertNotIn("## Later phases", prompt)
        self.assertNotIn("## Data model", prompt)


if __name__ == "__main__":
    unittest.main()
