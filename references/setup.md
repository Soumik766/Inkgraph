# Setup: new project or importing an existing novel

## New project

1. Ask the author (one message, only what's missing):
   - title, genre, POV and tense
   - word range per chapter (default 1800–3000)
   - 3–5 sample chapters of the target style: their own, or a reference author's
   - premise + endgame, if they have one
2. `$INK init <dir> --title "…" --genre "…" --pov "…" --tense … --words-min N --words-max N`
3. Save the samples as `bible/samples/sample-01.md`, etc.
4. Build `bible/style.md` from the samples (see "Style extraction" below). Show it to the author and revise until they agree.
5. Fill `bible/world.md` and `bible/outline.md` from what the author tells you. Don't invent world rules they didn't ask for. Leave gaps marked `TODO`.
6. Stage the starting cast (with tiers), places, factions, items, and the planned long-game threads in one `$INK batch` heredoc. Then `ink diff` → approval → `ink commit --setup --yes`.

## Style extraction

Read every sample in full. For each section of `style.md`, write **checkable rules** with evidence, for example:

- "Dialogue tags: almost only *said*; action beats instead of adverbs (sample-02: 41 tags, 37 *said*)."
- "Fights: short paragraphs, 1–2 sentences, sensory over choreography, no move names explained."
- "Chapter endings: final line is a single short sentence, usually a reveal or threat."

Run `$INK style` for the samples' measured fingerprint. Put the key numbers into `style.md` (average sentence length, short-sentence share, dialogue share, *said* share, dashes per 1k words), because every draft is checked against them. Copy the 2–3 most characteristic passages (≤300 words each) into the reference excerpts. Those excerpts travel with every drafting session, so pick them carefully.

If the samples are by a published author, use them only for style analysis. Never reuse their sentences, names, or plot in the draft.

## Importing an existing novel (chapters already written)

Never try to read 500 chapters in one go. Work in batches of 10–20:

1. Copy the chapters into `chapters/draft/ch-NNNN.md`.
2. For each chapter in order: read it, write its summary (`references/summaries.md`), stage its changes with one `$INK batch`, run `$INK diff -c N`, then commit. If the author agreed to batch approval, show the diffs for the whole batch of chapters together before committing them.
3. Every 50 chapters, do an arc rollup.
4. Run `$INK doctor` after each batch. At the end of each session, say how far the import got, so the next session resumes from `ink status`.
