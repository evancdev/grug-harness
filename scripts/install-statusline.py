#!/usr/bin/env python3
"""Points Claude Code's statusLine setting at statusline.py in this folder."""

import json
import os
import shlex
import stat
import sys
from pathlib import Path

from _lib import atomic_write


def main() -> None:
    statusline = Path(__file__).resolve().parent / "statusline.py"
    # Path.home() would turn an empty HOME into "/".
    config = os.environ.get("CLAUDE_CONFIG_DIR") or os.path.join(
        os.environ.get("HOME", ""), ".claude"
    )
    if not os.path.isabs(config):
        sys.exit(f"error: need an absolute HOME or CLAUDE_CONFIG_DIR, got {config!r}")
    if not statusline.is_file():
        sys.exit(f"error: {statusline} not found")
    # The command is the script's own path, so it needs the execute bits.
    statusline.chmod(
        statusline.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH
    )

    path = Path(config, "settings.json")
    try:
        settings = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        settings = {}
    except ValueError as e:
        sys.exit(f"error: {path} is not valid JSON: {e}")
    if not isinstance(settings, dict):
        sys.exit(f"error: {path} does not hold a JSON object")

    # Claude Code runs the command through a shell.
    entry = {"type": "command", "command": shlex.quote(str(statusline))}
    old = settings.get("statusLine")
    if old == entry:
        print(f"statusLine already runs {statusline}")
        return
    if old is not None:
        print(
            f"warning: replacing statusLine {json.dumps(old, ensure_ascii=False)}",
            file=sys.stderr,
        )
    settings["statusLine"] = entry
    atomic_write(path, json.dumps(settings, indent=2, ensure_ascii=False) + "\n")
    print(f"statusLine in {path} now runs {statusline}")


if __name__ == "__main__":
    try:
        main()
    except OSError as e:
        sys.exit(f"error: {e}")
