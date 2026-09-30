import json
import os
import re
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "statusline.py"
CHUNK_SIZE = 16384  # mirrors scripts/statusline.py
SGR = re.compile(r"\x1b\[[0-9;]*m")
HOOK = {"cwd": "/Users/me/widget", "model": {"display_name": "opus"}}
OPUS = "Opus 5 (1M context)"
# Python 3.14 still parses 100,000 levels; this depth raises RecursionError on
# every supported version.
DEEP = "[" * 1_000_000 + "]" * 1_000_000

Row = dict | str | bytes


def usage(input_tokens: object = 1, **fields: object) -> dict:
    return {"message": {"usage": {"input_tokens": input_tokens, **fields}}}


def turn(input_tokens: object = 1, **fields: object) -> dict:
    return {**usage(input_tokens), **fields}


FAILED_TURN = usage(0)
ROW = json.dumps(usage(7)).encode()


def run(stdin: bytes, stdout: int = subprocess.PIPE) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(SCRIPT)],
        input=stdin,
        stdout=stdout,
        stderr=subprocess.PIPE,
        timeout=10,
        check=False,
    )


def output(stdin: dict | str | bytes) -> str:
    if isinstance(stdin, dict):
        stdin = json.dumps(stdin)
    result = run(stdin.encode() if isinstance(stdin, str) else stdin)
    assert (result.returncode, result.stderr) == (0, b"")
    out = result.stdout.decode()
    assert out.count("\n") == 1, out
    return out


def line(stdin: dict | str | bytes) -> str:
    return SGR.sub("", output(stdin)).removesuffix("\n")


@pytest.fixture
def hook_for(tmp_path: Path) -> Callable[..., dict]:
    def build(*rows: Row, **hook: object) -> dict:
        path = tmp_path / "transcript.jsonl"
        with path.open("wb") as f:
            for row in rows:
                if isinstance(row, dict):
                    row = json.dumps(row)
                f.write(row if isinstance(row, bytes) else row.encode() + b"\n")
        return {**HOOK, **hook, "transcript_path": str(path)}

    return build


@pytest.mark.parametrize(
    ("cwd", "shown"),
    [
        ("/Users/me/widget", "widget"),
        ("/Users/me/widget///", "widget"),
        ("/", "/"),
        ("/Users/me/café 日本", "café 日本"),
        (None, ""),
    ],
)
def test_cwd_shows_last_folder_name(cwd, shown):
    assert line({"cwd": cwd}) == f"{shown} | claude | 0 tok"


@pytest.mark.parametrize(
    ("model", "shown"),
    [
        ({"display_name": "haiku"}, "haiku"),
        ("haiku", "claude"),
        ({"display_name": 42}, "claude"),
    ],
)
def test_model_shows_display_name(model, shown):
    assert line({"model": model}) == f" | {shown} | 0 tok"


def test_non_object_stdin_uses_defaults():
    assert line("[]") == " | claude | 0 tok"


@pytest.mark.parametrize(
    "stdin",
    [
        "{bad",
        pytest.param(DEEP, id="deeply-nested"),
        pytest.param(b'{"cwd": "/a/\xff"}', id="invalid-utf8"),
    ],
)
def test_unparseable_stdin_prints_error_line(stdin):
    assert line(stdin) == "claude json parsing error o7"


def test_unopenable_transcript_shows_0_tok(tmp_path):
    hook = {**HOOK, "transcript_path": str(tmp_path)}
    assert line(hook) == "widget | opus | 0 tok"


@pytest.mark.parametrize(
    ("total", "shown"),
    [
        (999, "999"),
        (1_000, "1.0k"),
        (1_449, "1.4k"),
        (1_450, "1.5k"),
        (999_949, "999.9k"),
        (999_950, "1.0M"),
    ],
)
def test_token_count_shows_k_and_m_units(hook_for, total, shown):
    assert line(hook_for(usage(total))) == f"widget | opus | {shown} tok"


@pytest.mark.parametrize(
    ("rows", "total"),
    [
        pytest.param([usage(10, cache_read_input_tokens=20, cache_creation_input_tokens=30, output_tokens=40)], 100, id="sums-all-four-fields"),
        pytest.param([usage(10, cache_read_input_tokens="9", cache_creation_input_tokens=-5, output_tokens=True)], 10, id="fields-that-are-not-counts-add-0"),
        pytest.param([usage(100), usage(15)], 15, id="last-usage-row-wins"),
        pytest.param([usage(100), usage(0, cache_read_input_tokens=500)], 500, id="fully-cached-turn-has-input-tokens-0"),
        pytest.param([usage(100), FAILED_TURN], 100, id="failed-turn-skipped"),
        pytest.param([usage(100), *(usage(n, output_tokens=9) for n in (None, True, -1, 2.0))], 100, id="row-skipped-unless-input-tokens-is-count"),
        pytest.param([usage(10), {"message": "hi"}, {"message": {"usage": "x"}}], 10, id="message-or-usage-not-object"),
        pytest.param([usage(10), "{bad"], 10, id="malformed-line-skipped"),
        pytest.param([usage(10), "[1, 2]"], 10, id="non-object-line-skipped"),
        pytest.param([usage(10), DEEP], 10, id="deeply-nested-line-skipped"),
        pytest.param([], 0, id="empty-transcript"),
    ],
)  # fmt: skip
def test_count_comes_from_newest_usable_row(hook_for, rows, total):
    assert line(hook_for(*rows)) == f"widget | opus | {total} tok"


@pytest.mark.parametrize(
    "data",
    [
        pytest.param(ROW, id="no-trailing-newline"),
        pytest.param(ROW + b"\r\n", id="crlf"),
        pytest.param(ROW + b"\n\xc3\x28\n", id="invalid-utf8"),
        pytest.param(b"\xef\xbb\xbf" + ROW + b"\n", id="utf8-bom"),
    ],
)
def test_byte_quirks_still_count(hook_for, data):
    assert line(hook_for(data)) == "widget | opus | 7 tok"


# Chunks are read backward, so the nearest boundary is CHUNK_SIZE bytes before
# the end of the file. `shift` moves the row's first or last byte across it.
@pytest.mark.parametrize("shift", [-1, 0, 1])
@pytest.mark.parametrize("edge", ["start", "end"])
def test_row_on_chunk_boundary_still_counts(hook_for, edge, shift):
    row = ROW + b"\n"
    tail = CHUNK_SIZE - (len(row) if edge == "start" else 0) + shift
    data = b"x" * CHUNK_SIZE + b"\n" + row + b"x" * (tail - 1) + b"\n"
    assert line(hook_for(data)) == "widget | opus | 7 tok"


@pytest.mark.parametrize(
    "rows",
    [
        pytest.param([usage(7), *["{}"] * 20_000], id="usage-row-many-chunks-back"),
        pytest.param([json.dumps(usage(7, pad="q" * CHUNK_SIZE * 3)).encode()], id="one-line-several-chunks-long"),
    ],
)  # fmt: skip
def test_row_beyond_first_chunk_still_counts(hook_for, rows):
    hook = hook_for(*rows)
    assert os.path.getsize(hook["transcript_path"]) > CHUNK_SIZE
    assert line(hook) == "widget | opus | 7 tok"


@pytest.mark.parametrize(
    ("total", "code"),
    [
        (199_999, 2),
        (200_000, 3),
        (299_999, 3),
        (300_000, 208),
        (399_999, 208),
        (400_000, 9),
    ],
)
def test_count_color_changes_at_band_edges(hook_for, total, code):
    assert f"\x1b[38;5;{code}m" in output(hook_for(usage(total)))


def test_only_count_and_unit_colored(hook_for):
    out = output(hook_for(usage(1_000)))
    assert out == "widget | opus | \x1b[38;5;2m1.0k tok\x1b[0m\n"


@pytest.mark.parametrize(
    ("model", "rows", "shown"),
    [
        pytest.param(OPUS, [turn(effort="xhigh")], "Opus 5 (xhigh) | 1", id="replaces-parenthetical"),
        pytest.param("Opus 5", [turn(effort="high")], "Opus 5 (high) | 1", id="appended-when-none"),
        pytest.param("Opus 5 (beta) (1M context)", [turn(effort="high")], "Opus 5 (beta) (high) | 1", id="only-last-parenthetical-replaced"),
        pytest.param("Opus (beta) 5", [turn(effort="high")], "Opus (beta) 5 (high) | 1", id="parenthetical-not-at-end-kept"),
        pytest.param(None, [turn(effort="high")], "claude (high) | 1", id="missing-name-uses-fallback"),
        pytest.param(OPUS, [turn(effort="high", perTurnEffort="xhigh")], "Opus 5 (xhigh) | 1", id="per-turn-wins"),
        pytest.param(OPUS, [turn(effort="high", perTurnEffort=3)], "Opus 5 (high) | 1", id="non-string-per-turn-falls-back"),
        pytest.param(OPUS, [turn(effort=3)], f"{OPUS} | 1", id="non-string-ignored"),
        pytest.param(OPUS, [usage()], f"{OPUS} | 1", id="none-leaves-name"),
        pytest.param(OPUS, [usage(7), {"effort": "xhigh"}], f"{OPUS} | 7", id="effort-on-row-without-usage-ignored"),
        pytest.param("Haiku 4.5", [turn(effort="xhigh"), turn(7, perTurnEffort=None)], "Haiku 4.5 | 7", id="newest-turn-without-effort-shows-none"),
        pytest.param(OPUS, [turn(effort="xhigh"), FAILED_TURN], "Opus 5 (xhigh) | 1", id="failed-turn-keeps-turn-before"),
    ],
)  # fmt: skip
def test_effort_shows_after_model_name(hook_for, model, rows, shown):
    hook = hook_for(*rows, model={"display_name": model})
    assert line(hook) == f"widget | {shown} tok"


def test_script_is_executable_with_shebang():
    # Claude Code runs the script directly, with no python3 in front.
    assert os.access(SCRIPT, os.X_OK)
    assert SCRIPT.read_text().startswith("#!")


def test_closed_stdout_exits_quietly():
    read_end, write_end = os.pipe()
    os.close(read_end)
    try:
        result = run(b"{}", stdout=write_end)
    finally:
        os.close(write_end)
    assert (result.returncode, result.stderr) == (1, b"")
