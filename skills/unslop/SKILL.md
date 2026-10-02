---
name: unslop
description: Cut AI tells from prose someone else will read. Use before a PR description, issue, brief, plan, README, commit message, or any other document leaves the terminal, and when asked to clean up a piece of writing. Two passes. Cut the sentences that tell the reader nothing they will use, then fix the word choices that mark text as AI-generated. The reply-level version runs as the baka! output style; this is the full rulebook with examples.
---

# Unslop

Two passes over the text. Cut first, then fix what survives. Polishing a sentence you were about to delete is wasted work.

## Do not touch

Unslop edits your own prose. It never rewrites:

- **Quoted material.** Error messages, log lines, the user's own words, another person's review comment. Paste verbatim, tells and all.
- **Real names.** Symbols, files, flags, commands, API fields, library names. `dangerouslySetInnerHTML` is not slop, it's the identifier.
- **Terms of art with no plain equivalent.** "Idempotent" and "race condition" mean something precise. Rule 21 targets metaphors dressed as jargon, not real vocabulary.

---

## Pass 1: cut

**Delete packaging, never content.**

A document is written for someone who has not seen the work. Its rationale, its testing strategy, and its scope explanation are content. What gets cut is the wrapper around them.

### The test

> Delete every sentence that tells the reader nothing they will act on or need to know.

Not a word budget. A word budget causes content loss; this doesn't.

### Cut list

C1. **Preamble.** Restating the title or the request in the first paragraph. Open with the point.
C2. **File-by-file diff summary.** A "## Changes" with one bullet per file, restating what the diff already shows. Say what changed *in behavior*, once.
C3. **Walking through code the reader will read.** If it needs a walkthrough, the code is wrong or the comment belongs in the file. Say what it does and why, not how it reads.
C4. **Hedging something you verified.** "It seems like the config might be missing." You read the file. It's missing. A hedge on a checked fact is false. Hedge only what you genuinely didn't verify, and say which it was. (Rule 19 handles stacked hedges as a word-choice tell; this is the separate failure of hedging a known fact.)
C5. **Double conclusion.** The point at the top, the same point restated at the bottom under a header.

### Never cut

- Why this approach and not the obvious alternative.
- What was tested, how, and what the output was. Failing output is pasted verbatim, never summarized.
- What is out of scope, what is still broken, what was assumed.
- `file:line` for every claim about the code.

---

## Pass 2: fix the words

Rewrite what survived. Preserve meaning, match the intended tone. Then self-audit once: "what makes this obviously AI-generated?" and fix what's left.

### Content

1. **Superficial -ing phrases.** "highlighting...", "ensuring...", "reflecting...", "showcasing...", "fostering...". Delete or expand with real sources.
2. **Vague attributions.** "Experts believe", "Industry reports suggest", "Some critics argue". Name the source or delete.

### Language

3. **AI vocabulary.** Additionally, crucial, delve, enduring, enhance, fostering, garner, interplay, intricate, landscape (abstract), pivotal, showcase, tapestry (abstract), testament, underscore, vibrant. Replace with plain words.
4. **Fancy ways to say "is".** "serves as", "stands as", "boasts", "features". Just say "is" or "has".
5. **"Not just X, but Y."** State the point directly instead.
6. **Rule of three.** Forcing ideas into groups of three. Use the natural number.
7. **Synonym cycling.** Protagonist, main character, central figure, hero all in one paragraph. Pick one, repeat it.
8. **False ranges.** "from X to Y" where X and Y aren't on a meaningful scale. List topics directly.

### Style

9. **Em dash overuse.** Avoid em dashes entirely. Use periods or commas only (no parentheses, no en dashes, no hyphen-as-dash substitutes). If a thought needs separation, end the sentence or use a comma.
10. **Colon overuse.** Colons are fine before a list or example. Not as mid-sentence connectors. "If you're coming from traditional automation: instead of registering event handlers, you describe conditions" adds nothing with the colon. Rewrite to let the point stand on its own without comparison framing. "Describing when the scheduler should fire works best as plain English." Same meaning, no crutch punctuation.
11. **Boldface overuse.** Don't bold every proper noun or acronym.
12. **Inline-header lists.** The tell is a bold label and colon that restates the line: "**Performance:** Performance improved...". Convert those to prose. A bold lead-in that ends in a period, names the item, and is followed by genuinely new detail ("**Schema in TypeScript.** Tables live in one file.") is fine, not a tell.
13. **Title case headings.** Use sentence case.
14. **Decorative emojis.** Remove from headings and bullets.
15. **Curly quotes.** Replace with straight quotes.

### Communication artifacts

16. **Chatbot phrases.** "I hope this helps!", "Let me know if...", "Of course!", "Certainly!", "Found the smoking gun!" Remove.
17. **Sycophantic tone.** "Great question! You're absolutely right!" Respond directly.

### Filler

18. **Filler phrases.** "In order to" becomes "To". "Due to the fact that" becomes "Because". "It is important to note that" gets deleted.
19. **Excessive hedging.** "could potentially possibly be argued that it might" becomes "may". One hedge maximum, and only on something you genuinely didn't verify.
20. **Generic conclusions.** "The future looks bright." State specific plans or facts.

### Jargon

21. **Abstract metaphor nouns.** Substrate, wedge, vector, locus, vantage, nexus, primitive (as noun), harness (as metaphor), surface (as in "API surface"), bedrock, scaffolding (as metaphor), modality, paradigm, gold-plating, ratchet (as metaphor), evacuate (for moving code), endgame, north star, flywheel. These read as technical but usually have a plainer concrete word. "Substrate" becomes "base". "Wedge in" becomes "add". "Vector" becomes "way" or "method". "Gold-plating" becomes "more than the job needs". "Ratchet" becomes the mechanism's real name or "a limit that only tightens". "Evacuate" becomes "move out". "Endgame" becomes "the last phase". Pick the concrete word.

### Plain speech

22. **Say what it does, not how it feels.** "the database stays close at hand", "SQL you can read", "types that follow your schema" name a feeling. The fix names the mechanism or a number: "`.toSQL()` returns the exact string sent to the database", "a column rename fails the build". Ask what the sentence tells the reader to do or know, then write that. If you can't restate it as a concrete instruction, fact, or number, cut it. One more check: if the sentence could appear unchanged in another project's docs, it says nothing about this one. Cut it.
23. **Shorten or split dense sentences.** If the reader has to backtrack to parse a sentence, break it in two or drop clauses. One idea per sentence.
24. **Active voice.** Prefer it. Catch "is/are/was/were + past participle" and name the actor: "queries are validated" becomes "the compiler validates queries", "the file is parsed by the loader" becomes "the loader parses the file". Passive is fine only when the actor is unknown or genuinely doesn't matter.
25. **Cut adverbs, or use a stronger verb.** "runs quickly" becomes "is fast" or the number. "significantly improves" becomes the measured delta. An adverb propping up a weak verb means the verb is wrong.
26. **Prefer the plain word.** "utilize" becomes "use", "leverage" becomes "use", "facilitate" becomes "help", "numerous" becomes "many", "in the event that" becomes "if". The fancier synonym is rarely clearer.
27. **Mannered prose.** Metaphor or flourish where a literal phrase exists: rhetorical fragments for effect, personified code ("the plan holds it"), figurative verbs ("rides along", "stands on"), stock framing phrases. "A dial worth turning" becomes "a parameter worth varying". A plain maxim that states a real rule is fine ("if there is no proof of testing, it was not tested"); a decorative one is not. Say what you mean. Rule 21 covers the metaphor nouns.
28. **Symbol-speak.** Arrows, glyphs, and unexplained abbreviations that make the reader decode instead of read. "Parser rejects bad date → exit 2, no write" becomes "Parser rejects a bad date, exits 2, writes nothing." Clipped sentences are fine and often better. Spell out the arrows and the abbreviations, not the articles.
29. **Where to look and what you'll see.** When the text tells the reader to do something, write numbered steps. Each one names the place, a screen, a command, a file, and what the reader is looking for once they are there. A step that sends someone somewhere without saying what they are looking at is half a step. Put what each result means next to the step rather than waiting for them to report back. The list is the answer, so it needs no introduction. If you don't know where something lives, say so instead of guessing a path.

### Structure

30. **Forced parallelism.** Two unlike things dressed as a matched pair because the shape looks tidy. "The parser validates input; the renderer validates output" when the renderer does no such thing. Symmetry is a claim. Only make it when it's true.
31. **Transitional throat-clearing.** "That said,", "With that in mind,", "Importantly,", "Notably,", "To be clear,", "At a high level,". These announce a turn instead of taking it. Delete the phrase and keep the sentence. (Rule 18 covers "it is important to note that" only.)
32. **Invented structure.** Numbered markers, phases, tiers, or "Part 1 / Part 2" imposed on content that isn't sequenced or ranked. Numbering is information: use it when order matters to the reader and prose when it doesn't. The same goes for a table with one meaningful column and three filler ones.
33. **Heading echo.** The heading and the first sentence under it saying the same thing. "## Caching. This section covers caching." Cut the sentence, or cut the heading.
