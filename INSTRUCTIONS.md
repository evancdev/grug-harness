# Install grug

You need [Claude Code](https://code.claude.com/docs/en/setup) and [Homebrew](https://brew.sh).

1. Install Python. grug's scripts need Python 3.11 or newer, and macOS comes with 3.9.

   ```sh
   brew install python
   ```

2. Install the plugin:

   ```sh
   claude plugin install grug --marketplace evancdev/grug-harness
   ```

   The last line it prints is `Successfully installed plugin: grug@grug (scope: user)`.

3. Start a new Claude Code session, or restart an open one. That sets grug's status line, and every other open session shows it at the bottom right away. The session you just started may not show it until you restart it. If `~/.claude/settings.json` already has a `statusLine`, grug leaves it, so delete that entry first to get grug's.
