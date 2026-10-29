# Prose pass (de-AI): a separate step from continuity

Run this pass after the draft is complete and before `ink check`. It changes only the prose, never facts. If the author has a **humanizer** skill installed, load it and use it instead of this file. This file is the built-in fallback.

`bible/style.md` always overrides this list. If the author's style does something listed here, keep it.

## Cut or rewrite on sight
- Stock AI vocabulary: *tapestry, testament to, palpable, a symphony of, delve, intricate dance, unwavering, a beacon of, in the grand scheme, couldn't help but, a mix of X and Y, sent shivers down, the weight of (abstract noun)*
- Triads by reflex ("cold, calculating, and cruel"). Keep at most one per scene.
- "It wasn't X — it was Y" reversals. At most one per chapter.
- Em-dash pileups. Most become commas, periods, or a restructured sentence.
- Characters "letting out a breath they didn't know they were holding", eyes that "darken", smirks everywhere.
- Paragraphs that end on a moral, a summary of what just happened, or the character's feeling stated outright.
- Dialogue where everyone speaks in the same polished, complete sentences.
- Every scene ending on a dramatic one-liner. Save that for the chapter hook.

## Add
- Concrete, specific nouns over abstractions: what is on the table, what the wound smells like.
- Uneven rhythm: a long sentence, then a short one. Paragraphs of different sizes.
- Subtext: characters avoid, lie, misunderstand, answer a different question.
- One detail per scene that only this world, or this character, would have.
- Let the reader infer emotion from action. Name it rarely.

## Procedure
1. Run `$INK style -c N`. Each ⚠ shows where the draft drifts from the author's measured voice.
2. Read the whole draft once without editing. Mark the flat or generic passages.
3. Reread the reference excerpts in `style.md`.
4. Rewrite the marked passages in the author's voice. Don't add plot, and don't remove facts that the summary or graph depends on.
5. Rerun `$INK style -c N`, and check the word count is still in range.
