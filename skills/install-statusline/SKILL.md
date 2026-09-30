---
name: install-statusline
description: Point Claude Code's statusLine setting at this plugin's statusline script.
disable-model-invocation: true
allowed-tools: Bash("${CLAUDE_PLUGIN_ROOT}/scripts/install-statusline.py" 2>&1)
---

!`"${CLAUDE_PLUGIN_ROOT}/scripts/install-statusline.py" 2>&1`

Show the output above to the user as it is, and add nothing.
