"""Command implementations. Each takes (args, Project) — except init."""
import copy
import json
import shutil
import sys
from pathlib import Path

from . import ops as O
from . import views as V
from .store import Project, new_graph
from .util import (GONE, HOLD_RELS, STATE, InkError, chname, csv, die, dump, now, out, parse_kv, read,
                   strip_meta, words, write_atomic)

TEMPLATES = Path(__file__).resolve().parent.parent.parent / "templates"


# ───────────── setup ─────────────

SKILL_DIR = Path(__file__).resolve().parent.parent.parent


def init(a):
    root = Path(a.dir).resolve()
    if root == SKILL_DIR or SKILL_DIR in root.parents:
        die(f"refusing to create a novel inside the skill folder ({SKILL_DIR}) — "
            "your chapters would end up in the skill's git repo. Pick a folder outside it.")
    if (root / STATE / "graph.json").exists():
        die(f"already an inkgraph project: {root}")
    for d in ("bible/samples", "chapters/draft", "chapters/final", "summaries/chapters", "summaries/arcs",
              "graph", "export", STATE + "/snapshots"):
        (root / d).mkdir(parents=True, exist_ok=True)
    g = new_graph(a.title, a.genre or "", a.pov or "", a.tense or "", a.words_min, a.words_max)
    write_atomic(root / STATE / "graph.json", dump(g))
    write_atomic(root / STATE / "pending.json", "[]")
    for src, dst in (("style.md", "bible/style.md"), ("world.md", "bible/world.md"),
                     ("outline.md", "bible/outline.md"), ("CLAUDE.md", "CLAUDE.md")):
        if (TEMPLATES / src).exists() and not (root / dst).exists():
            write_atomic(root / dst, read(TEMPLATES / src).replace("{{TITLE}}", a.title))
    if not (root / ".gitignore").exists():
        write_atomic(root / ".gitignore", "export/\nstory-map.html\n.inkgraph/snapshots/\n*.tmp\n")
    out(f"created '{a.title}' at {root}",
        "next: add 3–5 sample chapters to bible/samples/, then build bible/style.md")


def config(a, P):
    if not a.pairs:
        out(*(f"{k} = {v}" for k, v in {**P.g["meta"], **P.cfg}.items() if k not in ("created", "schema")))
        return
    for k, v in parse_kv(a.pairs).items():
        target = P.cfg if k in P.cfg else P.g["meta"] if k in P.g["meta"] else None
        if target is None or k in ("created", "schema"):
            die(f"unknown setting '{k}'")
        cur = target[k]
        target[k] = (v.lower() in ("1", "true", "yes", "on")) if isinstance(cur, bool) else int(v) if isinstance(cur, int) else v
        out(f"{k} = {target[k]}")
    P.save()


# ───────────── staging ─────────────

def add(a, P):
    op = {"op": "add", "type": a.type, "name": a.name, "aliases": csv(a.aliases), "desc": a.desc or "",
          "attrs": parse_kv(a.attr), "chapter": a.chapter, "tier": a.tier}
    if a.id:
        op["id"] = a.id
    if a.status:
        op["status"] = a.status
    P.stage(op)


def set_(a, P):
    fields = {f: getattr(a, f) for f in ("status", "fate", "desc", "name", "tier") if getattr(a, f, None) is not None}
    P.stage({"op": "set", "id": a.entity, "fields": fields, "attrs": parse_kv(a.attr), "chapter": a.chapter, "note": a.note or ""})


def kill(a, P):
    P.stage({"op": "set", "id": a.entity, "fields": {"status": "dead", "fate": a.fate}, "attrs": {},
             "chapter": a.chapter, "note": a.note or ""})


def alias(a, P):
    P.stage({"op": "alias", "id": a.entity, "alias": a.alias})


def note(a, P):
    P.stage({"op": "note", "id": a.entity, "text": a.text, "chapter": a.chapter})


def link(a, P):
    P.stage({"op": "link", "a": a.a, "b": a.b, "rel": a.rel, "chapter": a.chapter, "note": a.note or ""})
    if a.mutual:
        P.stage({"op": "link", "a": a.b, "b": a.a, "rel": a.rel, "chapter": a.chapter, "note": a.note or ""})


def unlink(a, P):
    P.stage({"op": "unlink", "a": a.a, "b": a.b, "rel": a.rel, "chapter": a.chapter, "note": a.note or ""})


def move(a, P):
    P.stage({"op": "move", "item": a.item, "to": a.to, "rel": a.rel, "chapter": a.chapter, "note": a.note or ""})


def thread(a, P):
    text = a.note or a.text or ""
    if a.action == "open":
        P.stage({"op": "thread_open", "title": a.ref, "kind": a.kind, "chapter": a.chapter, "note": text,
                 "payoff_by": a.payoff_by, "involves": csv(a.involves)})
    elif a.action == "note":
        if not text:
            die("thread note needs text")
        P.stage({"op": "thread_note", "id": a.ref, "chapter": a.chapter, "note": text, "involves": csv(a.involves)})
    else:
        P.stage({"op": "thread_close", "id": a.ref, "chapter": a.chapter, "note": text,
                 "status": "abandoned" if a.action == "abandon" else "closed"})


def event(a, P):
    P.stage({"op": "event", "title": a.title, "chapter": a.chapter, "involves": csv(a.involves),
             "note": a.note or "", "when": a.when or ""})


# ───────────── review & commit ─────────────

def plan(P, ch):
    """Dry-run everything a commit would do. Returns dict with trial graph, descriptions, notes, blockers."""
    g = copy.deepcopy(P.g)
    touched, descs, errors, notes = set(), [], [], []
    for i, op in enumerate(P.pending, 1):
        try:
            descs.append(O.apply(g, op, touched))
        except InkError as e:
            errors.append(f"op #{i}: {e}")
    hits, text = {}, ""
    if ch is not None:
        draft = P.p("chapters/draft", chname(ch))
        summ = P.p("summaries/chapters", chname(ch))
        if str(ch) in P.g["chapters"]:
            errors.append(f"chapter {ch} is already committed (`ink undo` or pick another number)")
        if not draft.exists():
            errors.append(f"missing draft {P.rel(draft)}")
        if not summ.exists() or not strip_meta(read(summ)).strip():
            errors.append(f"missing chapter summary {P.rel(summ)}")
        if draft.exists():
            text = strip_meta(read(draft))
            hits = O.Matcher(g).find(text)
            ranked = sorted(hits, key=lambda x: -hits[x])
            notes.append("appearances: " + (", ".join(f"{g['entities'][x]['name']}×{hits[x]}" for x in ranked) or "none"))
            w = words(text)
            m = P.g["meta"]
            flag = " ⚠ out of range" if (m["words_min"] and w < m["words_min"]) or (m["words_max"] and w > m["words_max"]) else ""
            notes.append(f"words: {w} (target {m['words_min']}–{m['words_max']}){flag}")
            for eid in ranked:
                e = g["entities"][eid]
                d = O.died_in(e)
                if e["status"] in GONE and d and d < ch:
                    notes.append(f"⚠ {e['name']} is {e['status']} since ch{d} — confirm memory/flashback/mention")
            cands = O.new_name_candidates(g, text)
            if cands:
                notes.append("⚠ names not in graph: " + ", ".join(f"{k}×{v}" for k, v in cands) + " — add them or ignore")
    return {"g": g, "touched": touched, "descs": descs, "notes": notes, "errors": errors, "hits": hits, "text": text}


def diff(a, P):
    ch = a.chapter
    r = plan(P, ch)
    out(f"── diff: {len(P.pending)} staged op(s)" + (f" · chapter {ch}" if ch else "") + " ──")
    out(*(f"  {i}. {d}" for i, d in enumerate(r["descs"], 1))) if r["descs"] else out("  (no graph changes staged)")
    if r["notes"]:
        out(*(f"  · {x}" for x in r["notes"]))
    if ch is not None:
        summ = P.p("summaries/chapters", chname(ch))
        if summ.exists():
            out("", "  summary:", *("    " + x for x in strip_meta(read(summ)).strip().splitlines()))
    if r["errors"]:
        out("", "  BLOCKING:", *(f"  ✗ {e}" for e in r["errors"]))
        sys.exit(2)


def commit(a, P):
    ch = a.chapter
    if ch is None and not a.setup:
        die("pass -c N, or --setup for a worldbuilding-only commit")
    r = plan(P, ch)
    if r["errors"]:
        diff(a, P)
    if not a.yes:
        diff(a, P)
        if not sys.stdin.isatty():
            die("not committed: show this diff to the author, get approval, then rerun with --yes")
        if input("\napply? [y/N] ").strip().lower() != "y":
            die("aborted")
    snap = P.snapshot(f"ch{ch}" if ch else "setup")
    g, touched = r["g"], r["touched"]
    if ch is not None:
        hits = r["hits"]
        for eid in hits:
            e = g["entities"][eid]
            apps = e.setdefault("appearances", [])
            if ch not in apps:
                apps.append(ch)
                apps.sort()
            e["last_seen"] = max(e.get("last_seen") or 0, ch)
            e["first_seen"] = e.get("first_seen") or ch
        touched.update(hits)
        draft = P.p("chapters/draft", chname(ch))
        raw = read(draft)
        title = next((ln[2:].strip() for ln in raw.splitlines() if ln.startswith("# ")), f"Chapter {ch}")
        g["chapters"][str(ch)] = {"title": title, "words": words(raw),
                                  "entities": sorted(hits, key=lambda x: -hits[x]), "committed": now()}
        g["position"]["last_chapter"] = max(g["position"]["last_chapter"], ch)
        touched.add(f"c:{ch}")
        P.p("chapters/final").mkdir(parents=True, exist_ok=True)
        shutil.move(str(draft), str(P.p("chapters/final", chname(ch))))
    P.g = g
    P.save()
    entry = {"ts": now(), "chapter": ch, "ops": P.pending, "snapshot": snap.name}
    P.pending = []
    P.save_pending()
    hist = P.history() + [entry]
    P.prune_snapshots(hist)
    P.write_history(hist)
    if P.cfg.get("obsidian", True):
        V.render_obsidian(P, touched)
    out(f"committed {'chapter ' + str(ch) if ch else 'setup'}: {len(r['descs'])} change(s), "
        f"{len(r['hits'])} entities seen")
    last_arc_end = max([x["to"] or 0 for x in P.g["arcs"].values()] + [0])
    if ch and ch - last_arc_end >= P.cfg.get("rollup_every", 50):
        out(f"⚠ {ch - last_arc_end} chapters since the last arc summary — do a rollup (`ink rollup`)")


def discard(a, P):
    if a.index:
        if not 1 <= a.index <= len(P.pending):
            die("no such staged op")
        op = P.pending.pop(a.index - 1)
        out(f"dropped #{a.index} ({op['op']})")
    else:
        out(f"discarded {len(P.pending)} staged op(s)")
        P.pending = []
    P.save_pending()


def undo(a, P):
    hist = P.history()
    if not hist:
        die("nothing to undo")
    last = hist[-1]
    label = f"chapter {last['chapter']}" if last["chapter"] else "setup commit"
    if not last.get("snapshot") or not (P.snapdir / last["snapshot"]).exists():
        die(f"snapshot for the last commit ({label}) was pruned; raise keep_snapshots to undo further back")
    if P.pending:
        die("staged ops exist — commit or `ink discard` them first")
    if not a.yes:
        die(f"this reverts {label} and re-stages its {len(last['ops'])} op(s). Rerun with --yes")
    P.restore(last["snapshot"])
    (P.snapdir / last["snapshot"]).unlink()
    if last["chapter"] is not None:
        f = P.p("chapters/final", chname(last["chapter"]))
        if f.exists():
            shutil.move(str(f), str(P.p("chapters/draft", chname(last["chapter"]))))
    P.write_history(hist[:-1])
    P.__init__(P.root)
    P.pending = last["ops"]
    P.save_pending()
    if P.cfg.get("obsidian", True):
        V.render_obsidian(P)
    out(f"reverted {label}; chapter back in draft, {len(last['ops'])} op(s) re-staged (edit with `ink discard N`)")


# ───────────── reading ─────────────

def _summary(P, n):
    f = P.p("summaries/chapters", chname(n))
    return strip_meta(read(f)).strip() if f.exists() else None


def _arc_for(g, n):
    for k, arc in sorted(g["arcs"].items(), key=lambda kv: int(kv[0])):
        if arc["from"] <= n <= (arc["to"] or 10 ** 9):
            return k, arc
    return None, None


def context(a, P):
    """Prioritised retrieval bundle. With --max-chars, lowest-priority sections are trimmed first."""
    g = P.g
    E = g["entities"]
    n = a.chapter or P.last + 1
    m = g["meta"]
    S = []  # (priority 0=keep … 9=drop first, text)

    head = [f"# Context for chapter {n} — {m['title']}",
            f"{m.get('genre')} · POV {m.get('pov')} · {m.get('tense')} tense · {m['words_min']}–{m['words_max']} words",
            f"last committed: ch{P.last} · style: bible/style.md (read in full before drafting) · world: bible/world.md"]
    if P.pending:
        head.append(f"⚠ {len(P.pending)} staged op(s) not committed — run `ink diff`")
    if n > P.last + 1:
        head.append(f"⚠ chapters {P.last + 1}–{n - 1} are not committed yet")
    S.append((0, "\n".join(head)))

    ak, arc = _arc_for(g, n)
    if arc and P.p(arc["file"]).exists():
        S.append((2, f"## Arc {ak}: {arc['title']} (ch{arc['from']}–{arc['to'] or '…'})\n" + strip_meta(read(P.p(arc["file"]))).strip()))
        prev = g["arcs"].get(str(int(ak) - 1))
        if prev and P.p(prev["file"]).exists():
            lines = strip_meta(read(P.p(prev["file"]))).strip().splitlines()
            S.append((7, f"## Previous arc {int(ak) - 1}: {prev['title']}\n" + "\n".join(lines[:15])))

    done = sorted(int(c) for c in g["chapters"] if int(c) < n)
    recent = done[-(a.recent or P.cfg.get("context_recent", 3)):]
    if recent:
        S.append((1, "## Recent chapters\n" + "\n\n".join(
            f"### ch{c}: {g['chapters'][str(c)]['title']}\n{_summary(P, c) or '(no summary)'}" for c in recent)))

    inv, warn = [], []
    if a.involves:
        for x in csv(a.involves):
            try:
                inv.append(O.resolve(g, x))
            except InkError as e:
                warn.append(f"⚠ {e}")
    elif recent:
        inv = [x for x in g["chapters"][str(recent[-1])].get("entities", []) if x in E][:8]
        warn.append("(no --involves: using the main entities of the last chapter)")
    # pull in active holders/items of involved entities so possessions aren't forgotten
    extra_items = [r["b"] for r in g["relations"] if r["a"] in inv and r["rel"] in HOLD_RELS and r.get("until") is None and r["b"] not in inv]
    if inv:
        cards = [V.entity_card(g, x) for x in inv]
        if extra_items:
            cards.append("held items: " + "; ".join(f"{E[i]['name']} ({E[i]['status']})" for i in extra_items))
        S.append((1, "\n".join(["## Entities in play", *warn, *cards])))
        back = set()
        for x in inv:
            back.update([c for c in E[x].get("appearances", []) if c and c < n and c not in recent][-2:])
        if back:
            S.append((5, "## Their last appearances\n" + "\n\n".join(
                f"### ch{c}\n{s}" for c in sorted(back)[-a.max_back:] if (s := _summary(P, c)))))
        gone = [f"{E[x]['name']} ({E[x]['status']} since ch{O.died_in(E[x])})" for x in inv if E[x]["status"] in GONE]
        if gone:
            S.append((0, "⚠ GONE: " + ", ".join(gone) + " — memory, flashback, corpse or mention only"))
    elif warn:
        S.append((0, "\n".join(warn)))

    opens = [t for t in g["threads"].values() if t["status"] == "open"]
    if opens:
        invs = set(inv)
        rel = [t for t in opens if invs & set(t["involves"])]
        due = [t for t in opens if t.get("payoff_by") and int(t["payoff_by"]) <= n + 5]

        def tl(t):
            last = next((x["text"] for x in reversed(t["notes"]) if x["text"]), "")
            pay = f", payoff by ch{t['payoff_by']}" if t.get("payoff_by") else ""
            return f"- {t['title']} [{t['id']} · {t['kind']} · ch{t['planted']}{pay}]" + (f" — {last}" if last else "")
        if rel:
            S.append((1, "## Open threads touching these entities\n" + "\n".join(tl(t) for t in sorted(rel, key=lambda t: t["planted"] or 0))))
        if due:
            S.append((0, "⚠ payoff due within 5 chapters / overdue:\n" + "\n".join(tl(t) for t in due)))
        others = [t for t in opens if t not in rel and t not in due]
        if others:
            S.append((6, f"## Other open threads ({len(others)})\n" + "; ".join(f"{t['title']} [{t['id']}]" for t in others[:60])
                      + (f" … +{len(others) - 60}" if len(others) > 60 else "")))

    if a.outline and P.p("bible/outline.md").exists():
        S.append((4, "## Outline\n" + strip_meta(read(P.p("bible/outline.md"))).strip()))

    if a.max_chars:
        while sum(len(t) for _, t in S) > a.max_chars and any(p > 1 for p, _ in S):
            S.remove(max(S, key=lambda pt: pt[0]))
    out("\n\n".join(t for _, t in S))


def chapter_file(P, file, n):
    """A given file (relative to cwd, then to the project), else chapter n's draft, else its final."""
    if file:
        for p in (Path(file), P.p(file)):
            if p.exists():
                return p
        die(f"no such file {file}")
    for p in (P.p("chapters/draft", chname(n)), P.p("chapters/final", chname(n))):
        if p.exists():
            return p
    die(f"chapter {n} has no draft or final file")


def check(a, P):
    g = P.g
    n = a.chapter or P.last + 1
    path = chapter_file(P, a.file, n)
    text = strip_meta(read(path))
    issues, info = [], []
    w = words(text)
    m = g["meta"]
    if m["words_min"] and w < m["words_min"]:
        issues.append(f"length {w} < min {m['words_min']}")
    elif m["words_max"] and w > m["words_max"]:
        issues.append(f"length {w} > max {m['words_max']}")
    else:
        info.append(f"length {w} words ✓")
    hits = O.Matcher(g).find(text)
    E = g["entities"]
    info.append("entities: " + (", ".join(f"{E[x]['name']}×{c}" for x, c in sorted(hits.items(), key=lambda kv: -kv[1])) or "none"))
    for eid in hits:
        e = E[eid]
        if e["status"] in GONE:
            issues.append(f"{e['name']} is {e['status']} since ch{O.died_in(e)} ({e.get('fate') or 'no fate'}) — memory/flashback/mention?")
        elif e["status"] in ("missing", "sealed"):
            issues.append(f"{e['name']} is {e['status']} — does this chapter change that? stage it")
        if e["type"] == "character" and e.get("last_seen") and n - e["last_seen"] >= 100:
            info.append(f"{e['name']} returns after {n - e['last_seen']} chapters (last ch{e['last_seen']}) — re-anchor the reader")
    for r in g["relations"]:
        if r.get("until") is None and r["rel"] in HOLD_RELS and r["b"] in hits and E[r["b"]]["type"] == "item" and r["a"] not in hits:
            issues.append(f"{E[r['b']]['name']} appears but its holder {E[r['a']]['name']} doesn't — transfer? (`ink move`)")
    cands = O.new_name_candidates(g, text)
    if cands:
        info.append("names not in graph: " + ", ".join(f"{k}×{v}" for k, v in cands))
    out(f"── check {path.name} as chapter {n} ──", *(f"  · {x}" for x in info),
        *(f"  ⚠ {x}" for x in issues), *([] if issues else ["  no continuity flags"]))


def find(a, P):
    q = a.query.lower()
    g = P.g
    for eid, e in g["entities"].items():
        hay = " ".join([e["name"], *e.get("aliases", []), e.get("desc", ""), e.get("fate", ""),
                        json.dumps(e.get("attrs", {}))]).lower()
        if q in hay:
            out(f"entity  {eid:26} {e['type']:9} {e['status']:9} {e['name']}")
    for tid, t in g["threads"].items():
        if q in (t["title"] + " " + " ".join(x["text"] for x in t["notes"])).lower():
            out(f"thread  {tid:26} {t['status']:9} {t['title']}")
    for vid, v in g["events"].items():
        if q in (v["title"] + " " + v.get("note", "")).lower():
            out(f"event   {vid:26} ch{v['chapter']:<7} {v['title']}")
    if a.text:
        hits = 0
        for f in sorted(P.p("summaries").rglob("*.md")):
            for line in read(f).splitlines():
                if q in line.lower():
                    out(f"{f.stem:9} {line.strip()[:150]}")
                    hits += 1
                    if hits >= a.limit:
                        out(f"… (limit {a.limit}; use --limit)")
                        return


def show(a, P):
    eid = O.resolve(P.g, a.entity)
    e = P.g["entities"][eid]
    apps = [x for x in e.get("appearances", []) if x]
    out(V.entity_card(P.g, eid, hist=None), f"appearances ({len(apps)}): " + V.ranges(apps))


def threads(a, P):
    rows = sorted(P.g["threads"].values(), key=lambda t: (t["status"] != "open", t["planted"] or 0))
    for t in rows:
        if a.all or t["status"] == "open":
            tail = f"→ch{t['closed_in']}" if t["closed_in"] else (f" due ch{t['payoff_by']}" if t.get("payoff_by") else "")
            out(f"{t['status']:9} {t['kind']:10} ch{t['planted']}{tail:10} {t['id']:30} {t['title']}")


def list_(a, P):
    for eid, e in sorted(P.g["entities"].items(), key=lambda kv: (kv[1]["type"], kv[1].get("tier", 2), kv[1]["name"])):
        if (a.type and e["type"] != a.type) or (a.status and e["status"] != a.status) or (a.tier and e.get("tier", 2) != a.tier):
            continue
        out(f"{e['type']:9} t{e.get('tier', 2)} {e['status']:9} last ch{str(e.get('last_seen')):6} {eid:26} {e['name']}")


def status(a, P):
    g = P.g
    E = g["entities"].values()
    by = {}
    for e in E:
        by[e["type"]] = by.get(e["type"], 0) + 1
    drafts = sorted(f.stem for f in P.p("chapters/draft").glob("ch-*.md"))
    words_total = sum(c["words"] for c in g["chapters"].values())
    opn = sum(1 for t in g["threads"].values() if t["status"] == "open")
    out(f"{g['meta']['title']} — {g['meta'].get('genre')}",
        f"chapters: {len(g['chapters'])} committed (last ch{P.last}) · {words_total:,} words",
        "entities: " + (", ".join(f"{v} {k}" for k, v in by.items()) or "none")
        + f" · dead: {sum(1 for e in E if e['status'] == 'dead')}",
        f"relations: {sum(1 for r in g['relations'] if r.get('until') is None)} active · events: {len(g['events'])}"
        f" · threads: {opn} open / {len(g['threads'])}",
        f"arcs: {len(g['arcs'])} · drafts: {', '.join(drafts) or 'none'} · staged ops: {len(P.pending)}")
    last_arc_end = max([x["to"] or 0 for x in g["arcs"].values()] + [0])
    if P.last - last_arc_end >= P.cfg.get("rollup_every", 50):
        out(f"⚠ {P.last - last_arc_end} chapters since the last arc summary — `ink rollup`")


def doctor(a, P):
    g = P.g
    E = g["entities"]
    probs, warns = [], []
    for r in g["relations"]:
        if r["a"] not in E or r["b"] not in E:
            probs.append(f"relation references missing entity: {r}")
    for t in g["threads"].values():
        for x in t["involves"]:
            if x not in E:
                probs.append(f"thread {t['id']} involves missing entity {x}")
        if t["status"] == "open" and t.get("payoff_by") and int(t["payoff_by"]) < P.last:
            warns.append(f"thread overdue: {t['title']} (payoff by ch{t['payoff_by']}, now ch{P.last})")
    for k in g["chapters"]:
        if not P.p("chapters/final", chname(k)).exists():
            probs.append(f"ch{k} committed but chapters/final/{chname(k)} missing")
        if not P.p("summaries/chapters", chname(k)).exists():
            probs.append(f"ch{k} has no summary")
    for f in P.p("chapters/final").glob("ch-*.md"):
        if str(int(f.stem[3:])) not in g["chapters"]:
            warns.append(f"{f.name} is in final/ but was never committed")
    gaps = [c for c in range(1, P.last + 1) if str(c) not in g["chapters"]]
    if gaps:
        warns.append(f"uncommitted chapter numbers: {V.ranges(gaps)}")
    names = {}
    for e in E.values():
        for nm in (e["name"], *e.get("aliases", [])):
            names.setdefault(nm.lower(), []).append(e["id"])
    for nm, ids in names.items():
        if len(set(ids)) > 1:
            probs.append(f"name/alias '{nm}' shared by {', '.join(sorted(set(ids)))}")
    holders = {}
    for r in g["relations"]:
        if r.get("until") is None and r["rel"] in ("owns", "wields") and E.get(r["b"], {}).get("type") == "item":
            holders.setdefault(r["b"], []).append(r["a"])
    for item, hs in holders.items():
        if len(hs) > 1:
            warns.append(f"{E[item]['name']} has {len(hs)} active owners: {', '.join(E[h]['name'] for h in hs)}")
    for e in E.values():
        if e["type"] == "character" and e.get("tier", 2) == 1 and e["status"] == "alive" and e.get("last_seen") and P.last - e["last_seen"] >= 100:
            warns.append(f"main character {e['name']} unseen for {P.last - e['last_seen']} chapters")
        if e["status"] in GONE and not e.get("fate"):
            warns.append(f"{e['name']} is {e['status']} with no fate recorded")
    try:
        P.trial()
    except InkError as e:
        probs.append(str(e))
    out(*(f"✗ {x}" for x in probs), *(f"⚠ {x}" for x in warns))
    out("healthy" if not probs and not warns else f"{len(probs)} problem(s), {len(warns)} warning(s)")
    if probs:
        sys.exit(2)


def rollup(a, P):
    out(f"# Summaries ch{a.from_}–ch{a.to} → write summaries/arcs/arc-NN.md from these (see references/summaries.md)\n")
    for c in range(a.from_, a.to + 1):
        s = _summary(P, c)
        if s:
            out(f"## ch{c} {P.g['chapters'].get(str(c), {}).get('title', '')}", s, "")


def arc(a, P):
    k = str(a.number)
    f = f"summaries/arcs/arc-{a.number:02d}.md"
    P.g["arcs"][k] = {"title": a.title, "from": a.from_, "to": a.to, "file": f}
    if not P.p(f).exists():
        write_atomic(P.p(f), f"# Arc {a.number}: {a.title}\n\nTODO: key turns · end state of every major character · threads opened/closed/open\n")
    P.save()
    out(f"arc {k} '{a.title}' ch{a.from_}–{a.to or '…'} → {f}")


# ───────────── views ─────────────

def render(a, P):
    V.render_obsidian(P)
    out("regenerated graph/ (Obsidian notes)")


def graph(a, P):
    path = P.p(a.out or "story-map.html")
    V.build_viewer(P, path, threads=not a.no_threads)
    out(f"wrote {P.rel(path)} — open it in any browser (works offline)")


def export(a, P):
    path, n = V.export(P, a.format, a.from_, a.to, a.caps)
    out(f"exported {n} chapter(s) → {P.rel(path)}")
