import importlib.util
import io
import json
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "grug-bot.py"
_spec = importlib.util.spec_from_file_location("grug_bot", SCRIPT)
assert _spec is not None and _spec.loader is not None
bot = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(bot)

REPO = "me/widget"
PR = "https://github.com/me/widget/pull/7"
CLAIMED = "2026-10-01T10:00:00Z"
LABEL_ADD = ("POST", "repos/me/widget/issues/7/labels", ("-f", "labels[]=local"))
LABEL_DELETE = ("DELETE", "repos/me/widget/issues/7/labels/local", ())
CLOSED = {"kind": "closed", "pr": PR}


def item(
    kind="comment", id=1, body="@grug-bot fix it", login="me", at="2026-10-01T10:05:00Z"
):
    stamp = "submitted_at" if kind == "review" else "created_at"
    found = {
        "id": id,
        "user": {"login": login},
        "body": body,
        "html_url": f"{PR}#{kind}-{id}",
        stamp: at,
    }
    if kind == "review_comment":
        found |= {"path": "app.py", "line": 3}
    return found


def event(kind="comment", id=1, body="@grug-bot fix it"):
    found = {"kind": kind, "id": id, "pr": PR, "url": f"{PR}#{kind}-{id}", "body": body}
    if kind == "review_comment":
        found |= {"path": "app.py", "line": 3}
    return found


PATHS = {
    "comment": "issues/7/comments",
    "review_comment": "pulls/7/comments",
    "review": "pulls/7/reviews",
}


def kind_of(found):
    if "submitted_at" in found:
        return "review"
    return "review_comment" if "path" in found else "comment"


class FakeGitHub:
    """Answers the gh calls the script makes, and records every write."""

    def __init__(
        self,
        items=(),
        states=("closed",),
        labels=("local",),
        failing=(),
        delete_error=None,
    ):
        self.pages = {path: [] for path in PATHS.values()}
        for found in items:
            self.pages[PATHS[kind_of(found)]].append(found)
        self.states = list(states)
        self.labels = [{"name": name} for name in labels]
        # One entry per poll: whether that poll's first read fails.
        self.failing = list(failing)
        self.delete_error = delete_error
        self.writes = []
        self.sleeps = []

    def __call__(self, *args, token=None, stdin=None):
        if args[:2] == ("api", "-X"):
            assert token == "bot-token"
            method, endpoint, *rest = args[2:]
            self.writes.append((method, endpoint, tuple(rest), stdin))
            if method == "DELETE" and self.delete_error:
                raise bot.Failed(self.delete_error)
            return f"{PR}#reply\n"
        assert token is None
        if args == ("api", "user", "--jq", ".login"):
            return "me\n"
        if args[:3] == ("api", "--paginate", "--slurp"):
            if "issues/7/comments" in args[3] and self.failing and self.failing.pop(0):
                raise bot.Failed("gh: Bad Gateway (HTTP 502)")
            path = next(p for p in self.pages if f"repos/{REPO}/{p}?" in args[3])
            return json.dumps([self.pages[path]])
        if args == ("api", f"repos/{REPO}/pulls/7"):
            # The watch only ends on a PR state, so a broken one would spin.
            if not self.states:
                raise AssertionError("watch never ended")
            state = self.states.pop(0)
            head = {"ref": "feature", "repo": {"full_name": REPO}}
            return json.dumps({"state": state, "labels": self.labels, "head": head})
        raise AssertionError(f"unexpected gh call {args}")


@pytest.fixture
def github(monkeypatch, tmp_path):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", "session-a")
    monkeypatch.setattr(bot, "bot_token", lambda: "bot-token")
    monkeypatch.setattr(bot, "now", lambda: CLAIMED)

    def install(**kwargs):
        fake = FakeGitHub(**kwargs)
        monkeypatch.setattr(bot, "gh", fake)
        monkeypatch.setattr(bot.time, "sleep", fake.sleeps.append)
        return fake

    return install


def watch(capsys):
    code = bot.watch(REPO, 7)
    return code, [json.loads(line) for line in capsys.readouterr().out.splitlines()]


def state_file(home: Path, repo=REPO, number=7) -> Path:
    return home / ".local" / "state" / "grug" / "watch" / repo / f"{number}.json"


@pytest.mark.parametrize(
    ("kind", "reaction"),
    [
        pytest.param("comment", "issues/comments", id="conversation-comment"),
        pytest.param("review_comment", "pulls/comments", id="inline-comment"),
        pytest.param("review", None, id="review-gets-no-reaction"),
    ],
)
def test_mention_prints_event_reacts_and_releases_on_close(
    github, capsys, tmp_path, kind, reaction
):
    fake = github(items=[item(kind)])
    assert watch(capsys) == (0, [event(kind), CLOSED])
    reacted = [
        ("POST", f"repos/{REPO}/{reaction}/1/reactions", ("-f", "content=eyes"), None)
    ]
    assert fake.writes == [
        (*LABEL_ADD, None),
        *(reacted if reaction else []),
        (*LABEL_DELETE, None),
    ]
    assert not state_file(tmp_path).exists()


@pytest.mark.parametrize(
    ("found", "seen", "printed"),
    [
        pytest.param(item(body="thanks, @GRUG-BOT."), [], True, id="mention-mid-sentence-any-case"),
        pytest.param(item(body="ask @grug-botty"), [], False, id="longer-name"),
        pytest.param(item(body="mail me@grug-bot"), [], False, id="inside-word"),
        pytest.param(item(login="you"), [], False, id="other-user"),
        pytest.param(item(at="2026-10-01T09:59:59Z"), [], False, id="before-claim"),
        pytest.param(item(), ["comment:1"], False, id="already-answered"),
    ],
)  # fmt: skip
def test_only_new_owner_mentions_print(github, capsys, tmp_path, found, seen, printed):
    if seen:
        path = state_file(tmp_path)
        path.parent.mkdir(parents=True)
        path.write_text(json.dumps({"since": CLAIMED, "seen": seen}))
    github(items=[found])
    expected = [event(body=found["body"])] if printed else []
    assert watch(capsys) == (0, [*expected, CLOSED])


def test_mentions_print_oldest_first(github, capsys):
    github(
        items=[
            item(at="2026-10-01T10:07:00Z"),
            item("review", 2, at="2026-10-01T10:05:00Z"),
        ]
    )
    assert watch(capsys) == (0, [event("review", 2), event(), CLOSED])


def test_open_pr_keeps_watching_and_saves_progress(
    github, capsys, monkeypatch, tmp_path
):
    github(items=[item()], states=("open", "closed"))
    saved = []
    monkeypatch.setattr(
        bot.time,
        "sleep",
        lambda _: saved.append(json.loads(state_file(tmp_path).read_text())),
    )
    assert watch(capsys) == (0, [event(), CLOSED])
    assert saved == [{"since": CLAIMED, "seen": ["comment:1"], "session": "session-a"}]


def test_removed_label_ends_watch_leaving_label_off(github, capsys, tmp_path):
    fake = github(states=("open",), labels=())
    assert watch(capsys) == (0, [{"kind": "unlabeled", "pr": PR}])
    assert fake.writes == [(*LABEL_ADD, None)]
    assert not state_file(tmp_path).exists()


@pytest.mark.parametrize(
    ("failing", "states", "result", "sleeps"),
    [
        pytest.param((True, True, False, True, True), ("open", "closed"), (0, [CLOSED]), 5, id="success-resets-count"),
        pytest.param((True, True, True), (), (1, [{"kind": "error", "pr": PR, "message": "gh: Bad Gateway (HTTP 502)"}]), 2, id="stops-after-three-in-row"),
    ],
)  # fmt: skip
def test_failing_polls_retry_then_stop(github, capsys, failing, states, result, sleeps):
    fake = github(failing=failing, states=states)
    assert watch(capsys) == result
    assert fake.sleeps == [30] * sleeps


@pytest.mark.parametrize(
    ("inline", "endpoint"),
    [
        pytest.param(None, f"repos/{REPO}/issues/7/comments", id="conversation"),
        pytest.param(5, f"repos/{REPO}/pulls/7/comments/5/replies", id="review-thread"),
    ],
)
def test_reply_posts_body_as_bot(github, capsys, inline, endpoint):
    fake = github()
    bot.reply(REPO, 7, inline, "Renamed it.\n")
    stdin = json.dumps({"body": "Renamed it.\n"})
    assert fake.writes == [
        ("POST", endpoint, ("--input", "-", "--jq", ".html_url"), stdin)
    ]
    assert capsys.readouterr().out == f"{PR}#reply\n"


def test_blank_reply_posts_nothing(github):
    fake = github()
    with pytest.raises(bot.Failed, match="the reply on stdin is empty"):
        bot.reply(REPO, 7, None, " \n")
    assert fake.writes == []


@pytest.mark.parametrize(
    ("error", "raised"),
    [
        pytest.param(
            "gh: Label does not exist (HTTP 404)", False, id="label-already-gone"
        ),
        pytest.param("gh: Server Error (HTTP 500)", True, id="server-error"),
    ],
)
def test_release_tolerates_only_missing_label(github, tmp_path, error, raised):
    github(delete_error=error)
    path = state_file(tmp_path)
    path.parent.mkdir(parents=True)
    path.write_text("{}")
    if raised:
        with pytest.raises(bot.Failed, match="HTTP 500"):
            bot.release(REPO, 7)
    else:
        bot.release(REPO, 7)
    assert path.exists() == raised


def test_session_end_releases_only_that_sessions_prs(github, monkeypatch, tmp_path):
    fake = github()
    owners = {
        (REPO, 7): "session-a",
        (REPO, 8): "session-b",
        ("you/thing", 3): "session-a",
    }
    for (repo, number), session in owners.items():
        path = state_file(tmp_path, repo, number)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({"session": session}))
    monkeypatch.setattr(bot.sys, "stdin", io.StringIO('{"session_id": "session-a"}'))
    assert bot.session_end() == 0
    assert [w[1] for w in fake.writes] == [
        f"repos/{REPO}/issues/7/labels/local",
        "repos/you/thing/issues/3/labels/local",
    ]
    assert sorted(p.stem for p in (tmp_path / ".local").rglob("*.json")) == ["8"]


def test_push_sends_head_to_pr_branch_with_bot_token(github, monkeypatch):
    github()
    runs = []

    def run(args, env, check):
        runs.append((args, env["GH_TOKEN"]))
        return bot.subprocess.CompletedProcess(args, 0)

    monkeypatch.setattr(bot.subprocess, "run", run)
    assert bot.push(REPO, 7) == 0
    [(args, token)] = runs
    assert args[-3:] == [
        "push",
        "https://github.com/me/widget.git",
        "HEAD:refs/heads/feature",
    ]
    assert token == "bot-token"


@pytest.mark.parametrize(
    ("command", "error"),
    [
        pytest.param(None, "set GRUG_BOT_TOKEN_CMD to a command that prints a grug-bot token", id="unset"),
        pytest.param("false", "GRUG_BOT_TOKEN_CMD failed: ", id="command-fails"),
        pytest.param("true", "GRUG_BOT_TOKEN_CMD failed: ", id="prints-nothing"),
    ],
)  # fmt: skip
def test_unusable_token_command_fails(monkeypatch, command, error):
    if command is None:
        monkeypatch.delenv("GRUG_BOT_TOKEN_CMD", raising=False)
    else:
        monkeypatch.setenv("GRUG_BOT_TOKEN_CMD", command)
    with pytest.raises(bot.Failed) as raised:
        bot.bot_token()
    assert str(raised.value) == error


@pytest.mark.parametrize(
    ("url", "parsed"),
    [
        pytest.param(f"{PR}/files", (REPO, 7), id="pr-tab-url"),
        pytest.param("https://github.com/me/widget/issues/7", None, id="issue-url"),
    ],
)
def test_pr_argument_needs_pr_url(url, parsed):
    if parsed is None:
        with pytest.raises(bot.argparse.ArgumentTypeError):
            bot.pr_arg(url)
    else:
        assert bot.pr_arg(url) == parsed
