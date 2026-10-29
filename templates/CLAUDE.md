# {{TITLE}} — inkgraph project

This novel is managed by the **inkgraph** skill. Load that skill before any story work.

- Story state lives in `.inkgraph/graph.json` and changes only through `ink`. Never hand-edit `graph/` or `.inkgraph/`.
- Start of session: `ink status` (plus `ink doctor` for long sessions). Before drafting: `ink context -c N --involves "<names>"`.
- Voice: `bible/style.md` + `ink style -c N`. World laws: `bible/world.md`. Plan: `bible/outline.md`.
- A chapter is done only when committed: `ink batch` → `ink diff -c N` → author approves → `ink commit -c N --yes`.

## Author notes for Claude
(Standing instructions: things to never do, taboo tropes, running jokes, naming conventions…)
