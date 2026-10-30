# `ink` command reference

`INK="python3 <skill>/scripts/ink.py"`. Run from inside the project, or pass `--root DIR`.
An entity reference can be an id, a name, or an alias, and is case-insensitive. `-c N` is the chapter where the change happens.

## Stage (nothing changes until commit)

| command | effect |
|---|---|
| `add character "Lin Feng" --tier 1 --aliases "Feng,Young Master Lin" --desc "…" --attr realm="Qi 3" -c 1` | new entity. Types: character, location, faction, item, power, concept. Tier 1 main / 2 supporting (default) / 3 minor |
| `set lin-feng --attr realm="Foundation 1" --attr injury="left arm" --note "cliff breakthrough" -c 57` | attribute changes (`--attr k=-` removes one). Also `--status`, `--fate`, `--desc`, `--name`, `--tier` |
| `kill "Elder Mo" --fate "poisoned; body burned" -c 120` | death plus fate in one op |
| `set X --status missing -c 90` | character statuses: alive, dead, missing, unknown, sealed, transformed. Others: active, destroyed, lost, dormant, unknown |
| `alias lin-feng "Ghost of Azure Peak"` | extra name used for detection and lookup |
| `note lin-feng "lied to Su Yan about the pendant" -c 33` | a history fact with no field |
| `link A "sworn brother of" B --mutual -c 12` | relation (directional; `--mutual` adds both directions) |
| `unlink A owns "Jade Pendant" -c 200 --note "lost in the abyss"` | end a relation (kept in history) |
| `move "Jade Pendant" "Su Yan" -c 201 [--rel wields]` | item changes hands: ends every current holder's link and adds the new one |
| `thread open "Who forged the pendant?" --kind foreshadow --involves "Lin Feng,Jade Pendant" --payoff-by 400 -c 3` | plant a thread. Kinds: plot, foreshadow, mystery, promise, romance, rivalry, setup |
| `thread note <id> "second hint: Mo crest" [--involves "Mo Clan"] -c 88` | advance a thread |
| `thread close <id> --note "Elder Mo confesses" -c 395` / `thread abandon <id> -c N` | pay off, or drop on purpose |
| `event "Fall of Azure Sect" --involves "Azure Sect,Elder Mo" --when "Year 3, winter" -c 150` | turning point |
| `batch` (stdin heredoc or a file) | many of the above, one per line, validated in order, **all-or-nothing** |

## Review & commit

| command | effect |
|---|---|
| `diff -c N` | staged changes, detected appearances (with counts), word count, gone-character and unknown-name warnings, the summary, and blockers (exit 2 if anything blocks) |
| `commit -c N --yes [--no-verify]` | gzip snapshot → apply → draft moves to final → record appearances → regenerate the touched notes |
| `commit --setup --yes` | worldbuilding-only commit |
| `discard [i]` | drop all staged ops, or op #i |
| `undo --yes` | revert the last commit: the chapter goes back to draft and its ops are re-staged. Multi-level, up to `keep_snapshots` |

## Read

| command | effect |
|---|---|
| `status` | overview, plus a warning when an arc rollup is due |
| `doctor` | integrity checks (broken refs, missing summaries or finals, name collisions, double owners, overdue threads, main characters long unseen); exit 2 on problems |
| `context [-c N] [--involves a,b] [--recent 3] [--outline] [--max-chars 24000]` | prioritised retrieval bundle. `--max-chars` trims the lowest-priority sections first |
| `check [file] [-c N]` | continuity flags for a draft (facts only) |
| `style` · `style -c N` / `style FILE` | prose fingerprint of `bible/samples/`, or a draft compared to it (voice only) |
| `show X` | full card with all history and appearance ranges |
| `find Q [--text] [--limit 40]` | search entities, threads, and events (`--text` also searches summaries) |
| `list [--type character] [--status dead] [--tier 1]` · `threads [--all]` | listings |
| `rollup --from A --to B` · `arc N --title "…" --from A --to B` | arc summaries |
| `config [key=value …]` | settings: `keep_snapshots` (25), `obsidian` (true), `context_recent` (3), `rollup_every` (50), `pre_commit` (a shell command run before every chapter commit; `{chapter}` is substituted; a non-zero exit blocks the commit, `--no-verify` bypasses it), plus meta such as `words_min`, `words_max`, `pov` |

## Views & export

| command | effect |
|---|---|
| `graph [--out FILE] [--no-threads]` | `story-map.html`: one offline file, no internet needed |
| `render` | full rebuild of the Obsidian notes in `graph/` (commits update the touched notes automatically; set `obsidian=false` to switch off) |
| `export --format docx\|txt\|md [--from A --to B] [--caps]` | reads `chapters/final/` only, writes to `export/`. docx needs pandoc. `bible/reference.docx` styles Word output |
