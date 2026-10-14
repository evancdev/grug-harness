# grug-harness

## Skill descriptions

A skill's `description` says only when to use it: the requests, situations, or commands that should load it, and which other skill to pick it over when both could fit. How to run it, who runs it, and in what order go in the body of `SKILL.md`.

Claude reads every description to choose a skill, before it loads the body. An instruction in the description gets read without the steps that explain it, and it adds length to every session that never uses the skill.
