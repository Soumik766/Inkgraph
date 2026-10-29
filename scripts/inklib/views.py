"""Read-only views: entity cards, Obsidian notes (incremental), offline graph viewer, export."""
import json
import re
import shutil
import subprocess
from pathlib import Path

from .ops import died_in
from .util import chname, die, read, slug, strip_meta, write_atomic

VIEWER = Path(__file__).resolve().parent.parent / "viewer" / "viewer.html"


# ───────────── text cards (for context / show) ─────────────

def rel_lines(g, eid, active=True, limit=None, per_rel=10):
    """Relations grouped by type: '—rival of→ A, B, C (+4)'. Ended ones carry their chapter span."""
    E = g["entities"]
    rs = [r for r in g["relations"] if (r["a"] == eid or r["b"] == eid) and ((r.get("until") is None) == active)]
    if limit:
        rs = rs[-limit:]
    groups = {}
    for r in rs:
        out_ = r["a"] == eid
        other = E[r["b"] if out_ else r["a"]]["name"]
        if not active:
            other += f" (ch{r['since']}–ch{r['until']})"
        groups.setdefault((out_, r["rel"]), []).append(other)
    lines = []
    for (out_, rel), names in groups.items():
        more = f" (+{len(names) - per_rel})" if len(names) > per_rel else ""
        shown = ", ".join(names[-per_rel:])
        lines.append(f"—{rel}→ {shown}{more}" if out_ else f"←{rel}— {shown}{more}")
    return lines


def entity_card(g, eid, hist=6):
    e = g["entities"][eid]
    tier = {1: "main", 2: "supporting", 3: "minor"}.get(e.get("tier", 2), "")
    L = [f"### {e['name']}  [{eid}] — {e['type']}, {tier}, {e['status'].upper()}"]
    if e.get("aliases"):
        L.append("aka: " + ", ".join(e["aliases"]))
    if e.get("desc"):
        L.append(e["desc"])
    if e.get("fate"):
        L.append(f"FATE (ch{died_in(e)}): {e['fate']}")
    if e.get("attrs"):
        L.append("now: " + "; ".join(f"{k}={v}" for k, v in e["attrs"].items()))
    L.append(f"seen: ch{e.get('first_seen')}–ch{e.get('last_seen')} · {len(e.get('appearances', []))} chapters")
    a = rel_lines(g, eid, True)
    if a:
        L.append("relations: " + "; ".join(a))
    p = rel_lines(g, eid, False, limit=4)
    if p:
        L.append("past: " + "; ".join(p))
    h = [x for x in e["history"] if x["field"] != "created"]
    if hist is not None:
        h = h[-hist:]
    if h:
        L.append("changes:")
        for x in h:
            old = f"{x['old']} → " if x.get("old") not in (None, "") else ""
            note = f" ({x['note']})" if x.get("note") else ""
            L.append(f"  - ch{x['chapter']}: {x['field']}: {old}{x['new']}{note}")
    return "\n".join(L)


def ranges(nums):
    if not nums:
        return "none"
    parts, s, p = [], nums[0], nums[0]
    for x in list(nums[1:]) + [None]:
        if x is not None and x == p + 1:
            p = x
            continue
        parts.append(f"{s}" if s == p else f"{s}–{p}")
        if x is not None:
            s = p = x
    return ", ".join(parts)


# ───────────── Obsidian notes ─────────────

def _fm(d):
    L = ["---"]
    for k, v in d.items():
        if v is None or v == "" or v == []:
            continue
        L.append(f"{k}: {json.dumps(v, ensure_ascii=False)}")
    L.append("---")
    return "\n".join(L)


def render_obsidian(P, touched=None):
    """Regenerate notes in graph/. touched=None → full rebuild; else only those ids (+ chapter numbers)."""
    g = P.g
    gd = P.p("graph")
    if touched is None and gd.exists():
        shutil.rmtree(gd)
    gd.mkdir(exist_ok=True)
    E = g["entities"]

    def wl(eid):
        return f"[[{eid}|{E[eid]['name']}]]" if eid in E else eid

    ev_by, th_by = {}, {}
    for v in g["events"].values():
        for x in v["involves"]:
            ev_by.setdefault(x, []).append(v)
    for t in g["threads"].values():
        for x in t["involves"]:
            th_by.setdefault(x, []).append(t)
    rel_by = {}
    for r in g["relations"]:
        rel_by.setdefault(r["a"], []).append(r)
        rel_by.setdefault(r["b"], []).append(r)

    want = (lambda key: True) if touched is None else (lambda key: key in touched)

    for eid, e in E.items():
        if not want(eid):
            continue
        d = gd / (e["type"] + "s")
        d.mkdir(exist_ok=True)
        B = [_fm({"id": eid, "type": e["type"], "status": e["status"], "tier": e.get("tier", 2),
                  "aliases": e.get("aliases", []), "first_seen": e.get("first_seen"), "last_seen": e.get("last_seen"),
                  "tags": [e["type"], e["status"]]}), f"# {e['name']}", ""]
        if e.get("desc"):
            B += [e["desc"], ""]
        if e.get("fate"):
            B += [f"**Fate:** {e['fate']}", ""]
        if e.get("attrs"):
            B += ["## Now"] + [f"- **{k}:** {v}" for k, v in e["attrs"].items()] + [""]
        if rel_by.get(eid):
            B.append("## Relations")
            for r in rel_by[eid]:
                span = f"ch{r['since']}–" + (f"ch{r['until']}" if r.get("until") else "now")
                B.append(f"- {r['rel']} → {wl(r['b'])} ({span})" if r["a"] == eid else f"- ← {r['rel']} of {wl(r['a'])} ({span})")
            B.append("")
        if ev_by.get(eid):
            B += ["## Events"] + [f"- [[{v['id']}|{v['title']}]] (ch{v['chapter']})" for v in sorted(ev_by[eid], key=lambda v: v["chapter"] or 0)] + [""]
        if th_by.get(eid):
            B += ["## Threads"] + [f"- [[{t['id']}|{t['title']}]] — {t['status']}" for t in th_by[eid]] + [""]
        B.append("## History")
        for h in e["history"]:
            old = f"{h['old']} → " if h.get("old") not in (None, "") else ""
            note = f" — {h['note']}" if h.get("note") else ""
            B.append(f"- ch{h['chapter']}: {h['field']}: {old}{h['new']}{note}")
        apps = [x for x in e.get("appearances", []) if x]
        if apps:  # plain ranges: chapter notes already link here (see Backlinks), so no edge hairball
            B += ["", f"## Appears in {len(apps)} chapters", ranges(apps)]
        write_atomic(d / f"{eid}.md", "\n".join(B) + "\n")

    for t in g["threads"].values():
        if not want("t:" + t["id"]):
            continue
        d = gd / "threads"
        d.mkdir(exist_ok=True)
        B = [_fm({"type": "thread", "kind": t["kind"], "status": t["status"], "planted": t["planted"],
                  "payoff_by": t.get("payoff_by"), "closed_in": t.get("closed_in"), "tags": ["thread", t["status"]]}),
             f"# {t['title']}", "", "Involves: " + ", ".join(wl(x) for x in t["involves"]), "", "## Notes"]
        B += [f"- ch{x['chapter']}: {x['text']}" for x in t["notes"]]
        write_atomic(d / f"{t['id']}.md", "\n".join(B) + "\n")

    for v in g["events"].values():
        if not want("e:" + v["id"]):
            continue
        d = gd / "events"
        d.mkdir(exist_ok=True)
        B = [_fm({"type": "event", "chapter": v["chapter"], "when": v.get("when"), "tags": ["event"]}), f"# {v['title']}", ""]
        if v["chapter"]:
            B.append(f"Chapter [[{chname(v['chapter'])[:-3]}|{v['chapter']}]]")
        B += ["Involves: " + ", ".join(wl(x) for x in v["involves"]), "", v.get("note", "")]
        write_atomic(d / f"{v['id']}.md", "\n".join(B) + "\n")

    for k, c in g["chapters"].items():
        if not want(f"c:{k}"):
            continue
        d = gd / "chapters"
        d.mkdir(exist_ok=True)
        sp = P.p("summaries/chapters", chname(k))
        s = strip_meta(read(sp)).strip() if sp.exists() else ""
        B = [_fm({"type": "chapter", "chapter": int(k), "words": c["words"], "tags": ["chapter"]}),
             f"# {c['title']}", "", s, "", "Entities: " + ", ".join(wl(x) for x in c.get("entities", []))]
        write_atomic(d / chname(k), "\n".join(B) + "\n")

    if touched is None:
        write_atomic(gd / "README.md", "# Story graph (generated)\n\nRegenerated by `ink` — edit through the CLI. "
                     "Open as an Obsidian vault for Graph view, or run `ink graph` for the built-in viewer.\n")


# ───────────── offline graph viewer ─────────────

def _viewer_hist(e, keep_notes=40):
    """All state changes (needed to rewind to any chapter) + the most recent notes."""
    hs = [h for h in e["history"] if h["field"] != "created"]
    notes = [h for h in hs if h["field"] == "note"][-keep_notes:]
    keep = [h for h in hs if h["field"] != "note" or h in notes]
    return [[h["chapter"] or 0, h["field"], h.get("old", ""), h["new"], h.get("note", "")] for h in keep]


def viewer_data(P, threads=True):
    g = P.g
    E = g["entities"]
    ids = list(E)
    ix = {eid: i for i, eid in enumerate(ids)}
    nodes = []
    for eid in ids:
        e = E[eid]
        nodes.append({"id": eid, "n": e["name"], "t": e["type"], "s": e["status"], "tier": e.get("tier", 2),
                      "al": e.get("aliases", []), "desc": e.get("desc", ""), "fate": e.get("fate", ""),
                      "attrs": e.get("attrs", {}), "f": e.get("first_seen") or 0, "l": e.get("last_seen") or 0,
                      "d": died_in(e), "a": len(e.get("appearances", [])),
                      "h": _viewer_hist(e)})
    edges = [[ix[r["a"]], ix[r["b"]], r["rel"], r["since"] or 0, r.get("until")] for r in g["relations"]
             if r["a"] in ix and r["b"] in ix]
    co = coappearance(g, ix)
    th = []
    if threads:
        for t in g["threads"].values():
            th.append({"id": t["id"], "n": t["title"], "k": t["kind"], "s": t["status"], "f": t["planted"] or 0,
                       "c": t.get("closed_in"), "p": t.get("payoff_by"), "inv": [ix[x] for x in t["involves"] if x in ix],
                       "notes": [[x["chapter"], x["text"]] for x in t["notes"]][-20:]})
    ev = sorted(([v["chapter"] or 0, v["title"], [ix[x] for x in v["involves"] if x in ix], v.get("note", ""), v.get("when", "")]
                 for v in g["events"].values()), key=lambda x: x[0])
    chapters = {k: c["title"] for k, c in g["chapters"].items()}
    return {"title": g["meta"]["title"], "genre": g["meta"].get("genre", ""), "max": max(P.last, 1),
            "nodes": nodes, "edges": edges, "co": co, "threads": th, "events": ev, "chapters": chapters}


def coappearance(g, ix, per_chapter=12, keep=4, min_count=2):
    """Implicit links between entities that share chapters: each entity keeps its top `keep` partners.
    Returns [a, b, count, first_shared_chapter]."""
    pair = {}
    for k, c in g["chapters"].items():
        ents = [x for x in c.get("entities", [])[:per_chapter] if x in ix]
        ch = int(k)
        for i in range(len(ents)):
            for j in range(i + 1, len(ents)):
                a, b = ix[ents[i]], ix[ents[j]]
                key = (a, b) if a < b else (b, a)
                p = pair.get(key)
                if p:
                    p[0] += 1
                else:
                    pair[key] = [1, ch]
    best = {}
    for (a, b), (n, first) in pair.items():
        if n < min_count:
            continue
        for x in (a, b):
            best.setdefault(x, []).append((n, a, b, first))
    chosen = set()
    for x, lst in best.items():
        lst.sort(reverse=True)
        for n, a, b, first in lst[:keep]:
            chosen.add((a, b, n, first))
    return sorted([list(t) for t in chosen], key=lambda t: -t[2])


def build_viewer(P, out_path, threads=True):
    if not VIEWER.exists():
        die(f"viewer template missing: {VIEWER}")
    data = json.dumps(viewer_data(P, threads), ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    page = read(VIEWER).replace("/*__DATA__*/null", data).replace("__TITLE__", _esc(P.g["meta"]["title"]))
    write_atomic(out_path, page)
    return out_path


def _esc(s):
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


# ───────────── export ─────────────

def export(P, fmt, lo=None, hi=None, caps=False):
    files = sorted(P.p("chapters/final").glob("ch-*.md"))
    sel = [f for f in files if (lo is None or int(f.stem[3:]) >= lo) and (hi is None or int(f.stem[3:]) <= hi)]
    if not sel:
        die("no final chapters in range (export only reads chapters/final/)")
    title = P.g["meta"]["title"]
    a, b = int(sel[0].stem[3:]), int(sel[-1].stem[3:])
    base = P.p("export", f"{slug(title)}_ch{a}-{b}")
    base.parent.mkdir(exist_ok=True)
    parts = []
    for f in sel:
        t = strip_meta(read(f)).strip()
        if not re.match(r"#\s", t):
            t = f"# Chapter {int(f.stem[3:])}\n\n{t}"
        parts.append(t)
    md = "\n\n".join(parts) + "\n"
    if fmt == "md":
        out = base.with_suffix(".md")
        write_atomic(out, md)
    elif fmt == "txt":
        txt = re.sub(r"^#+\s*(.+)$", lambda m: m.group(1).upper() if caps else m.group(1), md, flags=re.M)
        txt = re.sub(r"(\*\*|__)(.+?)\1", r"\2", txt)
        txt = re.sub(r"(?<![\w*])[*_](?!\s)(.+?)(?<!\s)[*_](?![\w*])", r"\1", txt)
        txt = re.sub(r"^\s*(?:[*-]\s*){3,}$", "* * *", txt, flags=re.M)
        out = base.with_suffix(".txt")
        write_atomic(out, txt)
    else:
        if not shutil.which("pandoc"):
            die("pandoc not found — install it (https://pandoc.org/installing.html) or use --format txt/md")
        tmp = base.with_suffix(".tmp.md")
        write_atomic(tmp, md)
        out = base.with_suffix(".docx")
        cmd = ["pandoc", str(tmp), "-f", "markdown", "-o", str(out), "--metadata", f"title={title}"]
        ref = P.p("bible/reference.docx")
        if ref.exists():
            cmd += ["--reference-doc", str(ref)]
        try:
            subprocess.run(cmd, check=True)
        finally:
            tmp.unlink(missing_ok=True)
    return out, len(sel)
