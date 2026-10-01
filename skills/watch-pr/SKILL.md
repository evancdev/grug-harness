---
name: watch-pr
description: Watch a GitHub PR for the user's @grug-bot comments and answer them from this session, as grug-bot. Use right after this session opens a PR, or when the user says to watch a PR.
---

Watching puts the `local` label on the PR. The cloud workflow skips a PR with that label, so this session answers instead. Every command below runs `"${CLAUDE_PLUGIN_ROOT}/scripts/grug-bot.py"`, written `grug-bot.py` here.

## Start

Run `grug-bot.py watch <pr-url>` with the Monitor tool, `timeout_ms` 1800000, described as "@grug-bot mentions on PR #<number>". When the monitor expires, start it again with the same command. It keeps its place in a state file, so no mention is lost or answered twice.

If it stops with an error saying `GRUG_BOT_TOKEN_CMD` is not set, tell the user to add it under `env` in `~/.claude/settings.json`, naming a command that prints a grug-bot token.

## Each event

Each event is one JSON line with a `kind`.

`comment`, `review_comment`, or `review` means the user asked for something in `body`. A `review_comment` also has the `path` and `line` it sits on. The watcher has already put an eyes reaction on it, except on a review.

1. Say in the terminal which mention you are on, then do what it asks, as you would for a message typed here. Anything you would ask the user about, ask in the terminal.
2. If you changed code, commit as grug-bot with `git -c user.name='grug-bot[bot]' -c user.email='336202702+grug-bot[bot]@users.noreply.github.com' commit`, then run `grug-bot.py push <pr-url>`. Never use plain `git push`, which goes out under the user's own login.
3. Pipe a short answer to `grug-bot.py reply <pr-url>`: what you did, or what they asked. For a `review_comment`, add `--inline <id>` so it lands in that thread.

`closed` means the PR merged or closed, and the label is already gone. Stop watching.

`unlabeled` means the user removed the label to hand the PR to the cloud workflow. Stop watching, and do not start again unless they ask.

`error` means the watch stopped. Tell the user the `message`.

## Stop

To stop early, stop the monitor and run `grug-bot.py release <pr-url>`. When the session ends, a hook releases every PR it watched.
