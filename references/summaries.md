# Summary spec

Chapter summaries are the long-term memory. At chapter 2,000 you'll never reread chapter 40. You'll read its summary. So a fact left out of a summary or the graph is effectively lost.

## Chapter summary — `summaries/chapters/ch-NNNN.md`

Aim for 6–12 lines. Write facts, not prose. Use this shape:

```
POV: <who> · when: <in-world time> · where: <location>
- <beat 1: what happened, who did it, outcome>
- <beat 2>
- <beat 3–5>
STATE CHANGES: <injuries, power-ups, items gained/lost, deaths, secrets learned and by whom>
REVEALED TO READER (not to characters): <dramatic irony, foreshadowing planted>
LINES TO REMEMBER: <≤2 short lines of dialogue that may be called back later>
ENDS ON: <the hook>
```

Rules:
- Name every character who matters, by their canonical name.
- Record **who knows what**. Knowledge asymmetry is where long serials break first.
- Record numbers that may come back: amounts, ages, distances, ranks, days remaining.
- Note planted foreshadowing explicitly, even when it's subtle in the text.

## Graph updates per chapter (stage these alongside the summary)

Check each of these against the chapter before staging:
- New named characters, places, items, or factions → `add` (with `--tier`; give aliases so detection finds them)
- Status changes (death, missing, sealed, transformed) → `kill` / `set --status`
- Attribute changes (realm/rank, injury, location, allegiance, title) → `set --attr k=v`
- Relationships formed or broken → `link` / `unlink`
- Items changing hands → `move ITEM NEW_HOLDER`
- Threads planted, advanced, paid off, or abandoned → `thread open|note|close|abandon`
- Turning points → `event`

Put all of these in a single `$INK batch` heredoc.

## Arc summary — `summaries/arcs/arc-NN.md`

Every ~50 chapters, or when an arc ends: run `ink rollup --from A --to B`, then write the arc summary in about one page:
- 5–10 key turns in order
- for every major character: state at arc end (location, power, allegiance, what they know)
- threads opened, closed, and still open
- tone and style shifts, if any

Then `ink arc N --title "…" --from A --to B`.
