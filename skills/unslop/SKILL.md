---
name: unslop
description: Use before writing anything shared with people other than the user, like a PR description, issue, brief, plan, README, or commit message, and when asked to clean up a piece of writing.
---

# Unslop

Cut first, then fix the words. Polishing a sentence you were about to delete is wasted work.

Never rewrite quoted material (error messages, log lines, someone's own words), real names (symbols, files, flags, commands), or a term of art with no plain equivalent. `dangerouslySetInnerHTML` is the identifier, and "idempotent" is vocabulary, not slop.

## Cut

A document is for someone who hasn't seen the work, so its reasoning, its testing, and what it leaves out are content. Delete the wrapper around them: any sentence that tells the reader nothing they will act on or need to know.

That means no restating the title or the request up top, no file-by-file list of what the diff already shows, no walkthrough of code the reader will read, and no closing paragraph that repeats the opening. Say what changed in behavior, once. Don't hedge something you checked. "It seems like the config might be missing" is false once you've read the file. Hedge only what you didn't verify, say which, and hedge once at most.

Never cut why you chose this approach over the obvious one, what you tested and what it showed, or what is out of scope, still broken, or assumed. Paste failing output verbatim. Give `file:line` for every claim about the code.

## Fix the words

Rewrite what survived, keeping its meaning and tone, then ask once what still makes it read as AI-written, and fix that.

Say what it does, not how it feels. "SQL you can read" names a feeling; "`.toSQL()` returns the exact string sent to the database" names the mechanism. A sentence that could appear unchanged in another project's docs says nothing about this one.

Use plain words and active voice: "use", not "utilize" or "leverage", and "the compiler validates queries", not "queries are validated". Passive is fine only when nobody knows or cares who did it. Swap an adverb for a stronger verb or a number. Keep one idea per sentence, and split any sentence the reader has to reread.

Cut these tells:

- AI vocabulary: additionally, crucial, delve, enhance, foster, intricate, landscape, pivotal, showcase, tapestry, testament, underscore, vibrant.
- "Serves as" or "boasts" where "is" or "has" works.
- "-ing" tails like "highlighting..." or "ensuring...", and vague sources like "experts believe".
- "Not just X, but Y", forced groups of three, synonym cycling, and false ranges like "from X to Y".
- Metaphor nouns where a concrete word exists: substrate, wedge, vector, surface, scaffolding, paradigm, north star, flywheel.
- Mannered prose: personified code ("the plan holds it"), figurative verbs ("rides along"), rhetorical fragments. A plain saying that states a real rule is fine.
- Filler ("in order to", "due to the fact that") and throat-clearing ("That said,", "Importantly,").
- Chatbot phrases, flattery, and generic endings like "the future looks bright".

## Format

No em dashes or en dashes, and no parentheses or hyphens standing in for them. Use periods or commas. Colons go before a list or an example, never as a connector mid-sentence. No arrows or unexplained abbreviations: "rejects a bad date, exits 2, writes nothing", not "bad date → exit 2". Clipped sentences without "the" or "a" are fine. Use sentence case headings, straight quotes, and no emoji. Don't bold every proper noun.

A bold label that restates its line ("**Performance:** Performance improved...") is a tell. A bold lead-in that names the item and adds something new is fine.

Number only what happens in order. Don't invent phases, tiers, or tables with one real column, and don't make two unlike things look parallel. A heading and the sentence under it shouldn't say the same thing.

When the text tells the reader to do something, write numbered steps. Each names the place (a screen, a command, a file), what to look for there, and what each result means. If you don't know where something lives, say so.
