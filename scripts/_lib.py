"""Scripts import this with a bare `from _lib import`, which works because
Python puts the running script's folder on sys.path. Code outside scripts/
must add that folder first.
"""

import contextlib
import os
import shutil
import tempfile
from pathlib import Path


def atomic_write(path: Path, text: str) -> None:
    """Replace `path` with `text` so no reader ever sees half a file.

    A symlink is written through, so a dotfile manager keeps its link. An
    existing file keeps its permissions, and a new one gets 0600.
    """
    target = path.resolve()
    target.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(
        prefix=f"{target.name}.", suffix=".tmp", dir=target.parent
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(text)
            # Without this a crash after the rename can leave an empty file.
            f.flush()
            os.fsync(f.fileno())
        with contextlib.suppress(FileNotFoundError):
            shutil.copymode(target, tmp)
        os.replace(tmp, target)
    except BaseException:
        # BaseException so Ctrl-C mid-write still removes the temp file.
        with contextlib.suppress(OSError):
            os.unlink(tmp)
        raise
