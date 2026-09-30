import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"


@pytest.fixture
def installer(tmp_path: Path) -> Path:
    # The space checks that the command is shell-quoted.
    folder = tmp_path / "my plugin"
    folder.mkdir()
    for name in ("install-statusline.py", "_lib.py"):
        shutil.copy2(SCRIPTS / name, folder)
    (folder / "statusline.py").write_text("")
    return folder / "install-statusline.py"


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


@pytest.mark.parametrize(
    ("before", "warning"),
    [
        pytest.param(None, "", id="no-settings-file"),
        pytest.param({"model": "opus", "env": {"NAME": "café"}}, "", id="other-settings-kept"),
        pytest.param({"statusLine": None, "model": "opus"}, "", id="null-replaced-quietly"),
        pytest.param(
            {"statusLine": {"type": "command", "command": "/Users/me/café/old.py"}},
            'warning: replacing statusLine {"type": "command", "command": "/Users/me/café/old.py"}\n',
            id="other-command-replaced-with-warning",
        ),
    ],
)  # fmt: skip
def test_writes_entry_keeping_other_settings(installer, home, before, warning):
    path = settings_file(home)
    if before is not None:
        path.parent.mkdir()
        path.write_text(json.dumps(before), encoding="utf-8")
    result = install(installer, home)
    statusline = installer.with_name("statusline.py")
    assert result == (
        0,
        f"statusLine in {path} now runs {statusline}\n",
        warning,
    )
    after = {
        **(before or {}),
        "statusLine": {"type": "command", "command": f"'{statusline}'"},
    }
    assert (
        path.read_text(encoding="utf-8")
        == json.dumps(after, indent=2, ensure_ascii=False) + "\n"
    )


def test_second_run_changes_nothing(installer, home):
    install(installer, home)
    path = settings_file(home)
    before = path.stat().st_ino, path.read_bytes()
    result = install(installer, home)
    assert result == (
        0,
        f"statusLine already runs {installer.with_name('statusline.py')}\n",
        "",
    )
    assert (path.stat().st_ino, path.read_bytes()) == before


@pytest.mark.parametrize(
    ("data", "error"),
    [
        pytest.param(b"{bad", "is not valid JSON: Expecting property name enclosed in double quotes: line 1 column 2 (char 1)", id="not-json"),
        pytest.param(b"\xff{}", "is not valid JSON: 'utf-8' codec can't decode byte 0xff in position 0: invalid start byte", id="invalid-utf8"),
        pytest.param(b"\xef\xbb\xbf{}", "is not valid JSON: Unexpected UTF-8 BOM (decode using utf-8-sig): line 1 column 1 (char 0)", id="utf8-bom"),
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
