#!/usr/bin/env python3

import json
import os
import sys
from collections.abc import Iterator
from typing import BinaryIO, TypeGuard

_CHUNK_SIZE = 16384
_TOKEN_KEYS = (
    "input_tokens",
    "cache_read_input_tokens",
    "cache_creation_input_tokens",
    "output_tokens",
)
# 256-color codes: 2 green, 3 yellow, 208 orange, 9 red.
_BANDS = ((200_000, 2), (300_000, 3), (400_000, 208))
_OVER = 9
# RecursionError is how json rejects very deep nesting.
_BAD_JSON = (ValueError, RecursionError)


def _as_dict(x: object) -> dict[str, object]:
    return x if isinstance(x, dict) else {}


def _as_str(x: object) -> str:
    return x if isinstance(x, str) else ""


def _is_count(v: object) -> TypeGuard[int]:
    return isinstance(v, int) and not isinstance(v, bool) and v >= 0


def _lines_from_end(f: BinaryIO) -> Iterator[bytes]:
    pos = f.seek(0, os.SEEK_END)
    head = b""
    while pos > 0:
        size = min(_CHUNK_SIZE, pos)
        pos -= size
        f.seek(pos)
        lines = (f.read(size) + head).split(b"\n")
        # The first line may continue in the chunk before this one.
        head = lines.pop(0)
        yield from reversed(lines)
    yield head


def _scan_transcript(path: str) -> tuple[int, str]:
    # Transcripts reach tens of MB, so read from the end and stop at the
    # newest turn. Effort comes from that same row: a model without effort,
    # like Haiku, writes none, and an older row's effort would be stale.
    try:
        with open(path, "rb") as f:
            for line in _lines_from_end(f):
                try:
                    row = json.loads(line)
                except _BAD_JSON:
                    continue
                if not isinstance(row, dict):
                    continue
                usage = _as_dict(_as_dict(row.get("message")).get("usage"))
                if not _is_count(usage.get("input_tokens")):
                    continue
                total = sum(v for v in map(usage.get, _TOKEN_KEYS) if _is_count(v))
                # Claude Code logs a failed turn or a hit limit as a row that
                # counts nothing.
                if total:
                    return total, (
                        _as_str(row.get("perTurnEffort")) or _as_str(row.get("effort"))
                    )
    except OSError:
        pass
    return 0, ""


def _base_model(name: str) -> str:
    cut = name.rfind(" (")
    if cut > 0 and name.endswith(")"):
        return name[:cut]
    return name


def _fmt(n: int) -> str:
    # Promote to M once the rounded display would otherwise show "1000.0k".
    if n >= 999_950:
        return _fmt_unit(n, 1_000_000, "M")
    if n >= 1_000:
        return _fmt_unit(n, 1_000, "k")
    return str(n)


def _fmt_unit(n: int, divisor: int, suffix: str) -> str:
    # Integer math because round() and format() round half to even.
    scaled = (n * 10 + divisor // 2) // divisor
    return f"{scaled // 10}.{scaled % 10}{suffix}"


def _tokens(total: int) -> str:
    # Always colored: stdout is a pipe, never a tty, and Claude Code renders
    # the escape codes.
    code = next((c for limit, c in _BANDS if total < limit), _OVER)
    return f"\x1b[38;5;{code}m{_fmt(total)} tok\x1b[0m"


def main() -> None:
    try:
        # Bytes, because text-mode stdin under the C locale lets bad UTF-8 through.
        hook = _as_dict(json.loads(sys.stdin.buffer.read()))
    except _BAD_JSON:
        print("claude json parsing error o7")
        return

    cwd = _as_str(hook.get("cwd"))
    # "/" strips to "", so fall back to the raw value.
    cwd = os.path.basename(cwd.rstrip("/")) or cwd
    model = _as_str(_as_dict(hook.get("model")).get("display_name")) or "claude"

    total, effort = _scan_transcript(_as_str(hook.get("transcript_path")))
    if effort:
        model = f"{_base_model(model)} ({effort})"

    print(f"{cwd} | {model} | {_tokens(total)}")


if __name__ == "__main__":
    try:
        main()
        sys.stdout.flush()
    except BrokenPipeError:
        # Python flushes stdout again on exit, which would raise a second time.
        os.dup2(os.open(os.devnull, os.O_WRONLY), sys.stdout.fileno())
        sys.exit(1)
