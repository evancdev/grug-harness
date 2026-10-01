from pathlib import Path

import pytest

STYLES = Path(__file__).resolve().parent.parent / "output-styles"
FIELDS = {"name", "description", "keep-coding-instructions", "force-for-plugin"}
FLAGS = {"keep-coding-instructions", "force-for-plugin"}


# `claude plugin validate` does not read output styles, and Claude Code loads a
# style with a misspelled field or a frontmatter that fails to parse without an
# error, so a forced style stops being forced and nothing says so.
@pytest.mark.parametrize(
    "style",
    [pytest.param(path, id=path.name) for path in sorted(STYLES.glob("*.md"))],
)
def test_frontmatter_loads(style: Path) -> None:
    lines = style.read_text(encoding="utf-8").splitlines()
    assert lines[:1] == ["---"], "frontmatter must open on line 1"
    assert "---" in lines[1:], "frontmatter is never closed"
    for line in lines[1 : lines.index("---", 1)]:
        field, _, value = line.partition(": ")
        assert field in FIELDS and value, f"not a one-line known field: {line!r}"
        if value[0] in "\"'":
            assert len(value) > 1 and value.endswith(value[0]), (
                f"unclosed quote: {line!r}"
            )
        if field in FLAGS:
            assert value in ("true", "false"), f"not true or false: {line!r}"
