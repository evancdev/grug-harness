import os
import re
import stat

import pytest
from _lib import atomic_write


def fail_with(error):
    def fail(*args):
        raise error

    return fail


def test_new_file_gets_folders_and_0600(tmp_path):
    target = tmp_path / "a" / "b" / "settings.json"
    atomic_write(target, "new\n")
    assert target.read_text() == "new\n"
    assert stat.S_IMODE(target.stat().st_mode) == 0o600


def test_replace_syncs_and_copies_mode_before_rename(tmp_path, monkeypatch):
    target = tmp_path / "settings.json"
    target.write_text("old\n")
    target.chmod(0o640)
    events = []
    fsync, replace = os.fsync, os.replace

    def spy_fsync(fd):
        events.append(("fsync", os.fstat(fd).st_size))
        fsync(fd)

    def spy_replace(src, dst):
        events.append(("rename", stat.S_IMODE(os.stat(src).st_mode)))
        replace(src, dst)

    monkeypatch.setattr(os, "fsync", spy_fsync)
    monkeypatch.setattr(os, "replace", spy_replace)
    atomic_write(target, "new text\n")
    assert events == [("fsync", 9), ("rename", 0o640)]
    assert target.read_text() == "new text\n"


def test_symlink_is_written_through(tmp_path):
    real = tmp_path / "dotfiles" / "settings.json"
    real.parent.mkdir()
    real.write_text("old\n")
    link = tmp_path / "settings.json"
    link.symlink_to(real)
    atomic_write(link, "new\n")
    assert link.readlink() == real
    assert real.read_text() == "new\n"


@pytest.mark.parametrize(
    ("step", "error"),
    [
        pytest.param("fsync", KeyboardInterrupt, id="ctrl-c-mid-write"),
        pytest.param("replace", OSError, id="rename-fails"),
    ],
)
def test_failure_leaves_file_unchanged(tmp_path, monkeypatch, step, error):
    target = tmp_path / "settings.json"
    target.write_text("old\n")
    monkeypatch.setattr(os, step, fail_with(error))
    with pytest.raises(error):
        atomic_write(target, "new\n")
    assert list(tmp_path.iterdir()) == [target]
    assert target.read_text() == "old\n"


def test_failed_cleanup_raises_original_error(tmp_path, monkeypatch):
    error = OSError("rename failed")
    monkeypatch.setattr(os, "replace", fail_with(error))
    monkeypatch.setattr(os, "unlink", fail_with(OSError("unlink failed")))
    with pytest.raises(OSError) as caught:
        atomic_write(tmp_path / "settings.json", "new\n")
    assert caught.value is error
    [left] = tmp_path.iterdir()
    assert re.fullmatch(r"settings\.json\..+\.tmp", left.name)
    assert left.read_text() == "new\n"
