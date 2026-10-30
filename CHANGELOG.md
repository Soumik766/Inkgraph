# Changelog

## 0.3.0 — 2026-10-30
- `pre_commit` hook: a project-defined command runs before every chapter commit (`{chapter}` substituted); a non-zero exit blocks it. `ink commit --no-verify` bypasses it.

## 0.2.0 — 2026-10-29
First public release as **Inkgraph**.

- Story graph CLI (`ink`): staging, diff, approval-gated commit, multi-level undo, `batch` staging.
- Continuity checks: gone or missing entities, items without holders, new-name detection.
- `ink style`: prose fingerprint of the author's samples, and drift detection on drafts.
- Prioritised `context` bundles with `--max-chars` trimming.
- Offline story map: time-travel slider, state at any chapter, timeline lanes, focus mode, PNG export.
- Incremental Obsidian vault, Word/txt/Markdown export, `doctor` health checks.
- Safety: refuses to create novels inside the skill folder; the repo `.gitignore` guards against committing a book.
- Example project: *Ashes of Azure Peak* (8 chapters).
