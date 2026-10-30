---
name: inkgraph
description: Write, continue, and keep consistent a long novel or webnovel (hundreds to thousands of chapters) using a persistent story graph of characters, places, items, factions, relations, deaths and fates, plot threads, and events, plus chapter/arc summaries and a style bible built from the author's reference chapters. Use whenever the user wants to start a novel project, write or continue a chapter, check continuity, update or view the story graph/map, import existing chapters, or export the book to Word or plain text — including short asks like "next chapter" or "continue the story" inside an inkgraph project.
---

# Inkgraph

A novel is a folder. Its memory is a **story graph** changed only through the `ink` CLI, plus **summaries** you write. You can't hold 3,000 chapters in context. The graph and summaries make chapter 2,400 consistent with chapter 40, so their quality decides everything.

```
INK="python3 <this-skill-dir>/scripts/ink.py"      # stdlib only; pandoc optional for .docx
```
Every command: `references/cli.md`. Run commands from inside the project folder, or pass `--root DIR`.

## Non-negotiable rules

1. **Graph changes only through `ink`.** Never hand-edit `.inkgraph/` or `graph/`. `graph/` is regenerated.
2. **Stage → diff → author approves → commit.** Paste the full `ink diff -c N` output in chat and wait for an explicit yes. Only then run `ink commit -c N --yes`. To fix an op: `ink discard <i>` and re-stage it. Never pass `--yes` without approval.
3. **Prose and continuity are separate passes.** The draft and prose pass are about voice. `ink check` and staging are about facts.
4. **Export reads `chapters/final/` only.** A chapter becomes final only by being committed.
5. **Retrieve, don't bulk-read.** Use `ink context`, `ink show`, and `ink find`. Open an old chapter only to match a specific scene.

## Where am I?

- No `.inkgraph/` folder here or above → **Setup**. Follow `references/setup.md`.
- Otherwise run `$INK status`.
  - Staged ops exist → show `ink diff` and resolve them first.
  - A draft is waiting in `chapters/draft/` → ask whether to continue it or replace it.
  - Run `$INK doctor` at the start of a long session or after an import.

## Writing chapter N (the loop)

1. **Plan.** `$INK context -c N --involves "<names>"` (add `--outline` when planning arcs, and `--max-chars 24000` if the output is huge). Read `bible/style.md` in full, including its excerpts. If the author gave no beats, propose 3–5 in chat that fit the open threads and the outline, and get an OK. For several chapters at once, plan all their beats first, then run this loop once per chapter.
2. **Draft** to `chapters/draft/ch-NNNN.md`. Start with `# Chapter N: Title`. Stay inside the word range from `context`. Write in the style bible's voice.
3. **Prose pass.** `$INK style -c N` compares the draft's fingerprint (sentence and paragraph length, dialogue share, tags, dashes, adverbs, AI-tell phrases) with the author's samples. Rewrite until it reports no ⚠, or until each remaining one is deliberate. Use the `humanizer` skill if installed, else `references/prose-pass.md`. Wording only.
4. **Continuity.** `$INK check -c N`. Fix every ⚠, or confirm it's intentional (a flashback or memory). Every "names not in graph" entry gets an `add`, or is consciously ignored.
5. **Summary.** Write `summaries/chapters/ch-NNNN.md` per `references/summaries.md`, including who-knows-what and planted foreshadowing.
6. **Stage everything in one call.** Write all of this chapter's changes as lines for `$INK batch` (heredoc). The batch is all-or-nothing, and any error names the failing line. Use the checklist in `references/summaries.md`. Always include `-c N`.
7. **Diff → approval → commit.** `$INK diff -c N` → show it → yes → `$INK commit -c N --yes`. If the project has a `pre_commit` hook (`$INK config`) and it fails, fix what it reports and retry. Never pass `--no-verify` unless the author explicitly asks.
8. **Rollup.** When `commit` or `status` warns that ~50 chapters have no arc summary, do an arc rollup (`references/summaries.md`).

Example step 6:
```bash
$INK batch <<'EOF'
add character "Wei Shan" --tier 2 --desc "Medicine Hall steward" -c 2
kill "Elder Mo" --fate "Poisoned via tea Lin Feng brewed; body burned on Wei Shan's order" -c 2
unlink "Lin Feng" owns "Jade Pendant" --note "vanished overnight" -c 2
thread open "Who poisoned Elder Mo?" --kind mystery --involves "Elder Mo,Wei Shan" --payoff-by 30 -c 2
event "Death of Elder Mo" --involves "Elder Mo,Lin Feng,Wei Shan" -c 2
EOF
```

**Editing committed chapters.** For the last commit, `$INK undo --yes` puts the chapter back in draft and re-stages its ops. For older chapters, edit `chapters/final/…` directly, update its summary, and stage corrective ops with that chapter number.

## Other requests

- **"Show me the story map / graph"** → `$INK graph`, then send `story-map.html`. It's one self-contained offline file: chapter time-travel slider, state-at-chapter panel, deaths/events/threads timeline, search, focus mode, PNG export.
- **"What happened to X / where is X / who has Y"** → `$INK show X`, plus `$INK find X --text`.
- **Polish or fix an existing chapter** → load `chapter-doctor` if installed. Otherwise: `ink context` + `ink check`, then a prose pass.
- **Export** → `$INK export --format docx` (or `txt`, `md`; `--from/--to` for a range). `bible/reference.docx` controls Word styling.
- **Import an existing novel** → `references/setup.md` § Importing.

## Quality bar

- Canonical names in summaries and the graph. Aliases are for prose (add them with `ink alias` so detection finds them).
- Tiers: `1` main cast, `2` supporting, `3` walk-ons. Tier drives context priority and map size.
- Dead stays dead unless the author decides otherwise. Resurrection is an explicit `ink set X --status alive -c N --note "how"`.
- Every long-game twist in `bible/outline.md` has an open `foreshadow` thread with `--payoff-by`.
- If a request contradicts the graph (a dead character speaking, an item the hero no longer holds), say so before writing.
