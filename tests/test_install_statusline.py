import json
import os
import shlex
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"


def copy_plugin(folder: Path) -> Path:
    folder.mkdir(parents=True)
    for name in ("install-statusline.py", "_lib.py"):
        shutil.copy2(SCRIPTS / name, folder)
    (folder / "statusline.py").write_text("")
    return folder / "install-statusline.py"


@pytest.fixture
def installer(tmp_path: Path) -> Path:
    # The space checks that the command is shell-quoted.
    return copy_plugin(tmp_path / "my plugin")


@pytest.fixture
def cache(tmp_path: Path) -> Path:
    # Where Claude Code keeps each version of grug installed from GitHub.
    return tmp_path / "plugin cache" / "grug" / "grug"


@pytest.fixture
def home(tmp_path: Path) -> Path:
    (tmp_path / "home").mkdir()
    return tmp_path / "home"


def install(
    installer: Path, home: Path | str | None, **env: str
) -> tuple[int, str, str]:
    env["PATH"] = os.environ["PATH"]
    if home is not None:
        env["HOME"] = str(home)
    result = subprocess.run(
        [sys.executable, str(installer)],
        env=env,
        cwd=installer.parent.parent,
        capture_output=True,
        encoding="utf-8",
        timeout=10,
        check=False,
    )
    return result.returncode, result.stdout, result.stderr


def settings_file(home: Path) -> Path:
    return home / ".claude" / "settings.json"


def write_settings(home: Path, settings: object) -> str:
    path = settings_file(home)
    path.parent.mkdir()
    text = json.dumps(settings, ensure_ascii=False)
    path.write_text(text, encoding="utf-8")
    return text


def entry(statusline: Path, **extra: object) -> dict[str, object]:
    return {"type": "command", "command": shlex.quote(str(statusline)), **extra}


def orphan(version: Path) -> Path:
    # What `claude plugin update` leaves in the version folder it replaced.
    (version / "scripts").mkdir(parents=True, exist_ok=True)
    (version / "scripts" / "statusline.py").touch()
    (version / ".orphaned_at").write_text("1792019254167")
    return version / "scripts" / "statusline.py"


@pytest.mark.parametrize(
    ("home_env", "config_env", "shown"),
    [
        pytest.param(None, None, "'.claude'", id="home-unset"),
        pytest.param("/home/me", "config", "'config'", id="relative-config-dir"),
    ],
)
def test_relative_settings_folder_exits_1(
    tmp_path, installer, home_env, config_env, shown
):
    env = {} if config_env is None else {"CLAUDE_CONFIG_DIR": config_env}
    result = install(installer, home_env, **env)
    error = f"error: need an absolute HOME or CLAUDE_CONFIG_DIR, got {shown}\n"
    assert result == (1, "", error)
    assert list(tmp_path.iterdir()) == [installer.parent]


def test_old_python_exits_1(installer, home):
    code = (
        "import runpy, sys; sys.version_info = (3, 9, 6, 'final', 0);"
        " sys.version = '3.9.6 (default)';"
        " runpy.run_path(sys.argv[1], run_name='__main__')"
    )
    result = subprocess.run(
        [sys.executable, "-c", code, str(installer)],
        env={"PATH": os.environ["PATH"], "HOME": str(home)},
        capture_output=True,
        encoding="utf-8",
        timeout=10,
        check=False,
    )
    error = (
        "error: grug needs Python 3.11 or newer, and python3 is 3.9.6."
        " Run `brew install python`.\n"
    )
    assert (result.returncode, result.stdout, result.stderr) == (1, "", error)
    assert list(home.iterdir()) == []


def test_claude_config_dir_moves_settings_file(tmp_path, installer, home):
    config = tmp_path / "config"
    install(installer, home, CLAUDE_CONFIG_DIR=str(config))
    assert list(config.iterdir()) == [config / "settings.json"]
    assert list(home.iterdir()) == []


def test_non_file_statusline_exits_1(installer, home):
    statusline = installer.with_name("statusline.py")
    statusline.unlink()
    statusline.mkdir()
    result = install(installer, home)
    assert result == (1, "", f"error: {statusline} not found\n")
    assert list(home.iterdir()) == []


def test_statusline_gets_execute_bits(installer, home):
    statusline = installer.with_name("statusline.py")
    statusline.chmod(0o640)
    install(installer, home)
    assert oct(statusline.stat().st_mode & 0o777) == oct(0o751)


def test_executable_statusline_not_touched(installer, home):
    # A plugin folder can be read-only, so chmod runs only when it must.
    statusline = installer.with_name("statusline.py")
    statusline.chmod(0o755)
    before = statusline.stat().st_ctime_ns
    assert install(installer, home) == (0, "", "")
    assert statusline.stat().st_ctime_ns == before


@pytest.mark.parametrize(
    "before",
    [
        pytest.param(None, id="no-settings-file"),
        pytest.param({"model": "opus", "env": {"NAME": "café"}}, id="other-settings-kept"),
        pytest.param({"statusLine": None, "model": "opus"}, id="null-replaced"),
    ],
)  # fmt: skip
def test_writes_entry_keeping_other_settings(installer, home, before):
    if before is not None:
        write_settings(home, before)
    assert install(installer, home) == (0, "", "")
    statusline = installer.with_name("statusline.py")
    after = {
        **(before or {}),
        "statusLine": {"type": "command", "command": f"'{statusline}'"},
    }
    assert (
        settings_file(home).read_text(encoding="utf-8")
        == json.dumps(after, indent=2, ensure_ascii=False) + "\n"
    )


def test_byte_order_mark_accepted(installer, home):
    path = settings_file(home)
    path.parent.mkdir()
    path.write_bytes(b'\xef\xbb\xbf{"model": "opus"}')
    assert install(installer, home) == (0, "", "")
    after = json.loads(path.read_text(encoding="utf-8"))
    assert after == {
        "model": "opus",
        "statusLine": entry(installer.with_name("statusline.py")),
    }


def test_second_run_changes_nothing(installer, home):
    install(installer, home)
    path = settings_file(home)
    before = path.stat().st_ino, path.read_bytes()
    assert install(installer, home) == (0, "", "")
    assert (path.stat().st_ino, path.read_bytes()) == before


@pytest.mark.parametrize(
    "old",
    [
        pytest.param({"type": "command", "command": "/Users/me/café/old.py"}, id="other-command"),
        pytest.param({"type": "command", "command": 7}, id="command-not-a-string"),
        pytest.param("/Users/me/old.py", id="not-an-object"),
    ],
)  # fmt: skip
def test_other_statusline_left_alone(installer, home, old):
    statusline = installer.with_name("statusline.py")
    statusline.chmod(0o640)
    text = write_settings(home, {"statusLine": old})
    assert install(installer, home) == (0, "", "")
    assert settings_file(home).read_text(encoding="utf-8") == text
    assert oct(statusline.stat().st_mode & 0o777) == oct(0o640)


@pytest.mark.parametrize("replaced", [False, True], ids=["current", "replaced"])
def test_entry_for_this_copy_not_rewritten(cache, home, replaced):
    installer = copy_plugin(cache / "new" / "scripts")
    if replaced:
        orphan(cache / "new")
    write_settings(home, {"statusLine": entry(installer.with_name("statusline.py"))})
    path = settings_file(home)
    before = path.stat().st_ino, path.read_bytes()
    assert install(installer, home) == (0, "", "")
    assert (path.stat().st_ino, path.read_bytes()) == before


@pytest.mark.parametrize("deleted", [False, True], ids=["replaced", "deleted"])
def test_replaced_grug_copy_moves_to_this_one(cache, home, deleted):
    installer = copy_plugin(cache / "new" / "scripts")
    old = orphan(cache / "old")
    if deleted:
        shutil.rmtree(cache / "old")
    write_settings(home, {"statusLine": entry(old, padding=0)})
    assert install(installer, home) == (0, "", "")
    after = json.loads(settings_file(home).read_text(encoding="utf-8"))
    statusline = installer.with_name("statusline.py")
    assert after == {"statusLine": entry(statusline, padding=0)}


def test_live_grug_copy_left_alone(cache, home):
    # A session that started before an update runs this from the replaced
    # folder after /clear or a compaction, and must not move the setting back.
    installer = copy_plugin(cache / "old" / "scripts")
    orphan(cache / "old")
    live = copy_plugin(cache / "new" / "scripts").with_name("statusline.py")
    text = write_settings(home, {"statusLine": entry(live)})
    assert install(installer, home) == (0, "", "")
    assert settings_file(home).read_text(encoding="utf-8") == text


def test_replaced_copy_leaves_other_replaced_copy_alone(cache, home):
    # Two updates while old sessions run: neither old copy takes the setting.
    installer = copy_plugin(cache / "v1" / "scripts")
    orphan(cache / "v1")
    text = write_settings(home, {"statusLine": entry(orphan(cache / "v2"))})
    assert install(installer, home) == (0, "", "")
    assert settings_file(home).read_text(encoding="utf-8") == text


def test_replaced_copy_takes_over_deleted_one(cache, home):
    installer = copy_plugin(cache / "v1" / "scripts")
    orphan(cache / "v1")
    write_settings(
        home, {"statusLine": entry(cache / "v0" / "scripts" / "statusline.py")}
    )
    assert install(installer, home) == (0, "", "")
    after = json.loads(settings_file(home).read_text(encoding="utf-8"))
    assert after == {"statusLine": entry(installer.with_name("statusline.py"))}


def test_checkout_takes_over_replaced_github_copy(tmp_path, cache, home):
    installer = copy_plugin(tmp_path / "code" / "grug-harness" / "scripts")
    write_settings(home, {"statusLine": entry(orphan(cache / "old"))})
    assert install(installer, home) == (0, "", "")
    after = json.loads(settings_file(home).read_text(encoding="utf-8"))
    assert after == {"statusLine": entry(installer.with_name("statusline.py"))}


def test_checkout_leaves_live_sibling_alone(tmp_path, home):
    # Worktrees under a folder named grug/grug look like version folders.
    worktrees = tmp_path / "src" / "grug" / "grug"
    installer = copy_plugin(worktrees / "main" / "scripts")
    sibling = copy_plugin(worktrees / "feature" / "scripts").with_name("statusline.py")
    text = write_settings(home, {"statusLine": entry(sibling)})
    assert install(installer, home) == (0, "", "")
    assert settings_file(home).read_text(encoding="utf-8") == text


@pytest.mark.parametrize(
    "make",
    [
        pytest.param(lambda c: entry(c.parent.parent / "other" / "grug" / "old" / "scripts" / "statusline.py"), id="another-marketplace"),
        pytest.param(lambda c: entry(c.parent / "other" / "old" / "scripts" / "statusline.py"), id="another-plugin"),
        pytest.param(lambda c: entry(c / "old" / "scripts" / "other.py"), id="another-script"),
        pytest.param(lambda c: entry(c / "old" / "bin" / "statusline.py"), id="another-folder"),
        pytest.param(lambda c: {"type": "command", "command": shlex.quote(str(c / "old" / "scripts" / "statusline.py")) + " --flag"}, id="with-argument"),
        pytest.param(lambda c: {"type": "command", "command": "'" + str(c / "old" / "scripts" / "statusline.py")}, id="unclosed-quote"),
        pytest.param(lambda c: {"type": "command", "command": "grug/grug/old/scripts/statusline.py"}, id="relative-path"),
        pytest.param(lambda c: {**entry(c / "old" / "scripts" / "statusline.py"), "type": "other"}, id="not-a-command-type"),
    ],
)  # fmt: skip
def test_dead_lookalike_left_alone(cache, home, make):
    # None of these folders exist, so only the shape of the path decides.
    installer = copy_plugin(cache / "new" / "scripts")
    text = write_settings(home, {"statusLine": make(cache)})
    assert install(installer, home) == (0, "", "")
    assert settings_file(home).read_text(encoding="utf-8") == text


@pytest.mark.parametrize(
    ("data", "error"),
    [
        pytest.param(b"{bad", "is not valid JSON: Expecting property name enclosed in double quotes: line 1 column 2 (char 1)", id="not-json"),
        pytest.param(b"\xff{}", "is not valid JSON: 'utf-8' codec can't decode byte 0xff in position 0: invalid start byte", id="invalid-utf8"),
        pytest.param(b"[]", "does not hold a JSON object", id="not-an-object"),
    ],
)  # fmt: skip
def test_unusable_settings_left_untouched(installer, home, data, error):
    path = settings_file(home)
    path.parent.mkdir()
    path.write_bytes(data)
    result = install(installer, home)
    assert result == (1, "", f"error: {path} {error}\n")
    assert path.read_bytes() == data


def assert_one_line_error(path: Path, data: bytes, result: tuple[int, str, str]):
    code, out, err = result
    assert (code, out) == (1, "")
    # One line, not a traceback, since the user sees it at every session start.
    assert err.startswith(
        ("error: cannot write ", f"error: {path} is not valid JSON: ")
    )
    assert err.count("\n") == 1
    assert list(path.parent.iterdir()) == [path]
    assert path.read_bytes() == data


@pytest.mark.parametrize(
    "data",
    [
        pytest.param(b'{"deep": ' + b"[" * 1_000_000 + b"]" * 1_000_000 + b"}", id="too-deep"),
        pytest.param(b'{"limit": 1e400}', id="infinity"),
        pytest.param(b'{"name": "\\ud83d"}', id="lone-surrogate"),
    ],
)  # fmt: skip
def test_settings_that_cannot_round_trip_left_untouched(installer, home, data):
    path = settings_file(home)
    path.parent.mkdir()
    path.write_bytes(data)
    assert_one_line_error(path, data, install(installer, home))


def test_deep_settings_written_or_one_line_error(installer, home):
    # Python 3.11 can't read this, 3.12 reads it but can't write it back, and
    # 3.13 and later do both.
    path = settings_file(home)
    path.parent.mkdir()
    data = b'{"deep": ' + b"[" * 5_000 + b"]" * 5_000 + b"}"
    path.write_bytes(data)
    result = install(installer, home)
    if result[0] != 0:
        assert_one_line_error(path, data, result)
        return
    assert result == (0, "", "")
    after = json.loads(path.read_text(encoding="utf-8"))
    assert after["statusLine"] == entry(installer.with_name("statusline.py"))


def test_unreadable_settings_exits_1(installer, home):
    path = settings_file(home)
    path.mkdir(parents=True)
    result = install(installer, home)
    assert result == (1, "", f"error: [Errno 21] Is a directory: '{path}'\n")


def test_symlinked_installer_uses_real_folder(tmp_path, installer, home):
    link = tmp_path / "bin" / "install-statusline"
    link.parent.mkdir()
    link.symlink_to(installer)
    install(link, home)
    command = json.loads(settings_file(home).read_text())["statusLine"]["command"]
    assert command == f"'{installer.with_name('statusline.py')}'"
