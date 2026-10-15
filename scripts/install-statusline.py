#!/usr/bin/env python3
"""Points Claude Code's statusLine setting at statusline.py in this folder.

The plugin's SessionStart hook runs this every time a session starts. It sets
statusLine when there is none, and moves it off a grug copy that Claude Code
replaced or deleted, so the status line keeps working after an update. Any
other statusLine stays as it is. Claude Code adds a SessionStart hook's stdout
to the session, so nothing goes to stdout.
"""

import json
import os
import shlex
import stat
import sys
from pathlib import Path

_EXECUTE = stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH
# RecursionError is how json rejects very deep nesting.
_BAD_JSON = (ValueError, RecursionError)


def _stale_grug(old: dict, deleted_only: bool) -> bool:
    # An install from GitHub lives in <cache>/grug/grug/<version>/. An update
    # marks the old version folder with .orphaned_at, and Claude Code deletes
    # it 14 days later. Sessions that started before an update still run this
    # hook from an old folder. So a live folder is never taken over, and an
    # old copy takes over only a deleted one, or versions would keep swapping
    # the setting.
    command = old.get("command")
    if old.get("type") != "command" or not isinstance(command, str):
        return False
    try:
        words = shlex.split(command)
    except ValueError:
        return False
    if len(words) != 1:
        return False
    path = Path(words[0])
    version = path.parent.parent
    if not (
        path.is_absolute()
        and path.name == "statusline.py"
        and path.parent.name == "scripts"
        and version.parent.name == "grug"
        and version.parent.parent.name == "grug"
    ):
        return False
    if not version.is_dir():
        return True
    return not deleted_only and (version / ".orphaned_at").exists()


def main() -> None:
    # The hook runs whatever python3 comes first on PATH, which on a Mac
    # without Homebrew's Python is Apple's 3.9.
    if sys.version_info < (3, 11):  # noqa: UP036
        sys.exit(
            "error: grug needs Python 3.11 or newer, and python3 is"
            f" {sys.version.split()[0]}. Run `brew install python`."
        )
    # Imported after the version check, since _lib can use newer syntax.
    from _lib import atomic_write

    statusline = Path(__file__).resolve().parent / "statusline.py"
    # Path.home() would turn an empty HOME into "/".
    config = os.environ.get("CLAUDE_CONFIG_DIR") or os.path.join(
        os.environ.get("HOME", ""), ".claude"
    )
    if not os.path.isabs(config):
        sys.exit(f"error: need an absolute HOME or CLAUDE_CONFIG_DIR, got {config!r}")

    path = Path(config, "settings.json")
    try:
        # Claude Code reads a settings file that starts with a byte order mark.
        settings = json.loads(path.read_text(encoding="utf-8-sig"))
    except FileNotFoundError:
        settings = {}
    except _BAD_JSON as e:
        sys.exit(f"error: {path} is not valid JSON: {e}")
    if not isinstance(settings, dict):
        sys.exit(f"error: {path} does not hold a JSON object")

    # Claude Code runs the command through a shell.
    command = shlex.quote(str(statusline))
    replaced = (statusline.parent.parent / ".orphaned_at").exists()
    old = settings.get("statusLine")
    if isinstance(old, dict) and old.get("command") == command:
        new = None
    elif old is None:
        new = {"type": "command", "command": command}
    elif isinstance(old, dict) and _stale_grug(old, replaced):
        new = {**old, "command": command}
    else:
        return

    if not statusline.is_file():
        sys.exit(f"error: {statusline} not found")
    # The command is the script's own path, so it needs the execute bits.
    mode = statusline.stat().st_mode
    if mode & _EXECUTE != _EXECUTE:
        statusline.chmod(mode | _EXECUTE)
    if new is None:
        return
    settings["statusLine"] = new
    try:
        text = json.dumps(settings, indent=2, ensure_ascii=False, allow_nan=False)
        atomic_write(path, text + "\n")
    except _BAD_JSON as e:
        sys.exit(f"error: cannot write {path}: {e}")


if __name__ == "__main__":
    try:
        main()
    except OSError as e:
        sys.exit(f"error: {e}")
