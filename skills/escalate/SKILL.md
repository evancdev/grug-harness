---
name: escalate
description: Use whenever only the user can decide what happens next, like when a request could mean two things, the agreed approach doesn't work, the same fix keeps failing, or what you find contradicts the plan.
---

# Escalate

Ask every question with the AskUserQuestion tool, never in your final reply. Once the reply is sent the turn is over, so the user reads a question there as commentary, and answering it costs them a round trip you could have spent working.

## When to ask

Ask right away when going further would waste the work or build the wrong thing. That happens when the agreed approach doesn't work, the same fix keeps failing, the code doesn't match what you were told about it, or you are about to write something you have no way to check.

Anything else waits. Keep working, ask the open questions together at the next natural stop, and ask anything still open before the work goes up for review.

Never ask what you could find out yourself by reading a file, running a command, or searching the repo, or what the user already settled in this conversation. Don't ask "Should I proceed?" or "Does this look right?".

Every choice the user hasn't settled is a question, however sure you are. Don't pick one yourself and defend it later.

If the behavior is settled and only your code is wrong, fix it, check it, and keep going.

## Write the question

The user doesn't have the code in their head. Write the question as a short scenario in three parts: how the thing works today, what you hit, and the choice. Aim for two sentences, two sentences, and one line. Past that they skim and answer off the option labels alone.

Put a blank line between the parts. Inside a part, give every step its own line or write it as running sentences, never one stray line break. Put all of it in the question itself. Setup in your reply and the question in the prompt get read as two things, and they answer the one in front of them.

Say what actually happens, and end on what someone would notice, not on which part is at fault. Use the real name of each field, file, or key, with simple words for what it does and what changes for the user. A scenario you could paste into another session unchanged is too vague.

## Options

Give two to four, each a different outcome the user can picture. Two options that lead to the same experience are one option. When the choice is a yes or no, ask it as a yes or no.

Keep each label to one to five words. The description says what happens if they pick it, what they end up with, and what it costs them. Name what the option produces, not the type or flag that would produce it. An option with no cost isn't a real choice.

Put your pick first, mark it "(Recommended)", and say why in its description, so they can disagree with the reason. Being sure is no reason to skip the question. It's a reason to make your pick one click.

Use `preview` only to compare things side by side, like two layouts or two versions of some code. It works only when they can pick one option.

## After they answer

They answered without the full context, so before you act, check that the answer can work here and doesn't contradict something settled earlier.

If it holds, act on it. Don't restate it, ask them to confirm it, or reopen it because you're unsure.

If it doesn't hold, ask again right away. Name the part that doesn't work and what it conflicts with. Don't quietly carry out an answer that will break.

If they wrote in their own answer and it changes the shape of the work, say in one line what you now understand the task to be, then do it.
