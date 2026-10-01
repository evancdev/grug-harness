#!/usr/bin/env python3
"""Lets a local Claude session answer @grug-bot mentions on a PR, as grug-bot."""

import argparse
import json
import os
import re
import shlex
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

from _lib import atomic_write

# The cloud workflow skips a PR with this label.
LABEL = "local"
# The rule claude-code-action uses, so a comment means the same to both.
MENTION = re.compile(r"(^|\s)@grug-bot([\s.,!?;:]|$)", re.IGNORECASE)
PR_URL = re.compile(r"https://github\.com/([\w.-]+/[\w.-]+)/pull/(\d+)")
POLL_SECONDS = 30
# A watch that cannot reach GitHub this many polls in a row stops, so the
# session hears about it instead of trusting the silence.
MAX_FAILURES = 3
# Review bodies cannot take reactions.
REACTIONS = {"comment": "issues/comments", "review_comment": "pulls/comments"}
SOURCES = (
    ("comment", "issues/{n}/comments?since={since}&", "created_at"),
    ("review_comment", "pulls/{n}/comments?since={since}&", "created_at"),
    ("review", "pulls/{n}/reviews?", "submitted_at"),
)


class Failed(Exception):
    pass


def gh(*args: str, token: str | None = None, stdin: str | None = None) -> str:
    env = dict(os.environ)
    if token is not None:
        env["GH_TOKEN"] = token
    result = subprocess.run(
        ["gh", *args],
        env=env,
        input=stdin,
        capture_output=True,
        encoding="utf-8",
        check=False,
    )
    if result.returncode != 0:
        raise Failed(result.stderr.strip() or f"gh exited {result.returncode}")
    return result.stdout


def bot_token() -> str:
    command = os.environ.get("GRUG_BOT_TOKEN_CMD", "")
    if not command:
        raise Failed("set GRUG_BOT_TOKEN_CMD to a command that prints a grug-bot token")
    result = subprocess.run(
        shlex.split(command), capture_output=True, encoding="utf-8", check=False
    )
    if result.returncode != 0 or not result.stdout.strip():
        raise Failed(f"GRUG_BOT_TOKEN_CMD failed: {result.stderr.strip()}")
    return result.stdout.strip()


def as_bot(method: str, endpoint: str, *args: str, stdin: str | None = None) -> str:
    return gh("api", "-X", method, endpoint, *args, token=bot_token(), stdin=stdin)


def pr_arg(url: str) -> tuple[str, int]:
    match = PR_URL.match(url)
    if not match:
        raise argparse.ArgumentTypeError(f"not a GitHub PR URL: {url!r}")
    return match[1], int(match[2])


def watch_dir() -> Path:
    return Path.home() / ".local" / "state" / "grug" / "watch"


def state_path(repo: str, number: int) -> Path:
    return watch_dir() / repo / f"{number}.json"


def read_state(path: Path) -> dict | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None
    except ValueError as e:
        raise Failed(f"{path} is not valid JSON: {e}") from None


def save_state(path: Path, state: dict) -> None:
    atomic_write(path, json.dumps(state) + "\n")


def now() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def emit(event: dict) -> None:
    print(json.dumps(event, ensure_ascii=False), flush=True)


def poll(repo: str, number: int, login: str, state: dict) -> tuple[list[dict], dict]:
    url = f"https://github.com/{repo}/pull/{number}"
    found = []
    for kind, endpoint, stamp in SOURCES:
        path = endpoint.format(n=number, since=state["since"])
        pages = json.loads(
            gh("api", "--paginate", "--slurp", f"repos/{repo}/{path}per_page=100")
        )
        for item in (item for page in pages for item in page):
            if (
                (item.get("user") or {}).get("login") == login
                and (item.get(stamp) or "") >= state["since"]
                and f"{kind}:{item['id']}" not in state["seen"]
                and MENTION.search(item.get("body") or "")
            ):
                mention = {
                    "kind": kind,
                    "id": item["id"],
                    "pr": url,
                    "url": item["html_url"],
                    "body": item["body"],
                }
                if kind == "review_comment":
                    mention |= {"path": item["path"], "line": item.get("line")}
                found.append((item[stamp], mention))
    pr = json.loads(gh("api", f"repos/{repo}/pulls/{number}"))
    return [mention for _, mention in sorted(found, key=lambda f: f[0])], pr


def watch(repo: str, number: int) -> int:
    url = f"https://github.com/{repo}/pull/{number}"
    path = state_path(repo, number)
    try:
        login = gh("api", "user", "--jq", ".login").strip()
        state = read_state(path) or {"since": now(), "seen": []}
        state["session"] = os.environ.get("CLAUDE_CODE_SESSION_ID", "")
        save_state(path, state)
        as_bot(
            "POST", f"repos/{repo}/issues/{number}/labels", "-f", f"labels[]={LABEL}"
        )
        failures = 0
        while True:
            try:
                mentions, pr = poll(repo, number, login, state)
            except Failed:
                failures += 1
                if failures == MAX_FAILURES:
                    raise
                time.sleep(POLL_SECONDS)
                continue
            failures = 0
            for mention in mentions:
                emit(mention)
                state["seen"].append(f"{mention['kind']}:{mention['id']}")
                save_state(path, state)
                if mention["kind"] in REACTIONS:
                    comments = REACTIONS[mention["kind"]]
                    endpoint = f"repos/{repo}/{comments}/{mention['id']}/reactions"
                    try:
                        as_bot("POST", endpoint, "-f", "content=eyes")
                    except Failed as e:
                        print(f"warning: no reaction: {e}", file=sys.stderr)
            if pr["state"] != "open":
                emit({"kind": "closed", "pr": url})
                release(repo, number)
                return 0
            # Removing the label by hand hands the PR to the cloud workflow.
            if LABEL not in {label["name"] for label in pr["labels"]}:
                emit({"kind": "unlabeled", "pr": url})
                path.unlink(missing_ok=True)
                return 0
            time.sleep(POLL_SECONDS)
    except (Failed, OSError) as e:
        emit({"kind": "error", "pr": url, "message": str(e)})
        return 1


def reply(repo: str, number: int, inline: int | None, body: str) -> None:
    if not body.strip():
        raise Failed("the reply on stdin is empty")
    if inline is None:
        endpoint = f"repos/{repo}/issues/{number}/comments"
    else:
        endpoint = f"repos/{repo}/pulls/{number}/comments/{inline}/replies"
    posted = as_bot(
        "POST",
        endpoint,
        "--input",
        "-",
        "--jq",
        ".html_url",
        stdin=json.dumps({"body": body}),
    )
    print(posted.strip())


def push(repo: str, number: int) -> int:
    head = json.loads(gh("api", f"repos/{repo}/pulls/{number}"))["head"]
    if head["repo"] is None:
        raise Failed("the PR's branch is gone")
    # Over https with the bot's token, whatever origin points at, so the push
    # never goes out under the user's own login.
    helper = '!f() { echo username=x-access-token; echo "password=$GH_TOKEN"; }; f'
    return subprocess.run(
        [
            "git",
            "-c",
            "credential.helper=",
            "-c",
            f"credential.helper={helper}",
            "push",
            f"https://github.com/{head['repo']['full_name']}.git",
            f"HEAD:refs/heads/{head['ref']}",
        ],
        env={**os.environ, "GH_TOKEN": bot_token()},
        check=False,
    ).returncode


def release(repo: str, number: int) -> None:
    try:
        as_bot("DELETE", f"repos/{repo}/issues/{number}/labels/{LABEL}")
    except Failed as e:
        if "HTTP 404" not in str(e):
            raise
    state_path(repo, number).unlink(missing_ok=True)


def session_end() -> int:
    try:
        session = json.load(sys.stdin).get("session_id")
    except (ValueError, AttributeError) as e:
        raise Failed(f"hook input is not a JSON object: {e}") from None
    status = 0
    for path in sorted(watch_dir().glob("*/*/*.json")):
        repo = f"{path.parent.parent.name}/{path.parent.name}"
        try:
            state = read_state(path)
            if session and state and state.get("session") == session:
                release(repo, int(path.stem))
        except (Failed, OSError, ValueError) as e:
            print(f"error: {repo}#{path.stem}: {e}", file=sys.stderr)
            status = 1
    return status


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    command = commands.add_parser(
        "watch", help="label the PR, then print each new mention as a JSON line"
    )
    command.add_argument("pr", type=pr_arg)
    command = commands.add_parser("reply", help="post stdin on the PR")
    command.add_argument("pr", type=pr_arg)
    command.add_argument(
        "--inline",
        type=int,
        metavar="ID",
        help="answer in this review comment's thread",
    )
    command = commands.add_parser("push", help="push HEAD to the PR's branch")
    command.add_argument("pr", type=pr_arg)
    command = commands.add_parser("release", help="remove the label and stop watching")
    command.add_argument("pr", type=pr_arg)
    commands.add_parser(
        "session-end", help="SessionEnd hook: release the PRs the session watched"
    )
    args = parser.parse_args()

    if args.command == "session-end":
        return session_end()
    repo, number = args.pr
    if args.command == "watch":
        return watch(repo, number)
    if args.command == "push":
        return push(repo, number)
    if args.command == "reply":
        reply(repo, number, args.inline, sys.stdin.read())
    else:
        release(repo, number)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (Failed, OSError) as e:
        sys.exit(f"error: {e}")
