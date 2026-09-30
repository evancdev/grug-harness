import re
from pathlib import Path

import pytest

SKILL = Path(__file__).resolve().parent.parent / "skills" / "unslop" / "SKILL.md"
TEXT = SKILL.read_text(encoding="utf-8")
RULES = re.findall(r"^(C?)(\d+)\. \*\*(.+?)\.?\*\*", TEXT, re.MULTILINE)
TITLES = {prefix + number: title for prefix, number, title in RULES}
NUMBER = r"(C?\d+)"
REFERENCE = rf"\b[Rr]ules? {NUMBER}"

# Found by the words after the number, so a renumber that carries the
# references along still passes.
CROSS_REFERENCES = [
    pytest.param(
        "Rule {} targets metaphors",
        "Abstract metaphor nouns",
        id="terms-of-art-points-at-metaphor-nouns",
    ),
    pytest.param(
        "Rule {} handles stacked hedges",
        "Excessive hedging",
        id="hedged-fact-points-at-excessive-hedging",
    ),
    pytest.param(
        "Rule {} covers the metaphor nouns",
        "Abstract metaphor nouns",
        id="mannered-prose-points-at-metaphor-nouns",
    ),
    pytest.param(
        'Rule {} covers "it is important',
        "Filler phrases",
        id="throat-clearing-points-at-filler-phrases",
    ),
]


@pytest.mark.parametrize(
    "prefix",
    [
        pytest.param("C", id="cut-list-counts-up-from-C1"),
        pytest.param("", id="numbered-rules-count-up-from-1"),
    ],
)
def test_rules_numbered_from_1_without_gaps(prefix):
    numbers = [int(number) for p, number, _ in RULES if p == prefix]
    assert numbers
    assert numbers == list(range(1, len(numbers) + 1))


@pytest.mark.parametrize(("reference", "title"), CROSS_REFERENCES)
def test_cross_reference_names_intended_rule(reference, title):
    before, after = reference.split("{}")
    pattern = re.escape(before) + NUMBER + re.escape(after)
    assert [TITLES.get(number) for number in re.findall(pattern, TEXT)] == [title]


def test_every_cross_reference_pinned():
    assert len(re.findall(REFERENCE, TEXT)) == len(CROSS_REFERENCES)
