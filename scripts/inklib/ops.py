"""Graph operations (the only code that mutates story state) + name resolution and matching."""
import re

from .util import CHAR_STATUS, OTHER_STATUS, THREAD_KINDS, TYPES, InkError, slug


# ───────────── resolution ─────────────

def resolve(g, ref):
    E = g["entities"]
    if ref in E:
        return ref
    r = ref.strip().lower()
    s = slug(ref)
    if s in E:
        return s
    for eid, e in E.items():
        if e["name"].lower() == r or any(a.lower() == r for a in e.get("aliases", ())):
            return eid
    raise InkError(f"unknown entity '{ref}' (try `ink find {ref}`)")


def resolve_thread(g, ref):
    T = g["threads"]
    if ref in T:
        return ref
    s = slug(ref)
    if s in T:
        return s
    for tid, t in T.items():
        if t["title"].lower() == ref.strip().lower():
            return tid
    raise InkError(f"unknown thread '{ref}' (see `ink threads`)")


def died_in(e):
    for h in reversed(e["history"]):
        if h["field"] == "status" and h["new"] in ("dead", "destroyed"):
            return h["chapter"]
    return None


# ───────────── name matching (fast, single pass) ─────────────

_TOK = re.compile(r"[A-Za-z0-9]+")


class Matcher:
    """Finds entity mentions in text with one tokenization pass and n-gram dict lookups.
    Character names must be capitalised in the text; other types match case-insensitively."""

    def __init__(self, g):
        self.idx = {}
        self.maxn = 1
        for eid, e in g["entities"].items():
            cap = e["type"] == "character"
            for name in (e["name"], *e.get("aliases", ())):
                key = tuple(t.lower() for t in _TOK.findall(name))
                if not key:
                    continue
                self.idx.setdefault(key, []).append((eid, cap))
                self.maxn = max(self.maxn, len(key))

    def find(self, text):
        toks = [m.group(0) for m in _TOK.finditer(text)]
        low = [t.lower() for t in toks]
        hit = {}
        for i in range(len(toks)):
            for n in range(min(self.maxn, len(toks) - i), 0, -1):
                ents = self.idx.get(tuple(low[i:i + n]))
                if not ents:
                    continue
                capped = all(t[0].isupper() or t[0].isdigit() for t in toks[i:i + n])
                for eid, cap in ents:
                    if capped or not cap:
                        hit[eid] = hit.get(eid, 0) + 1
                break
        return hit  # eid -> mention count


_STOP = set("""I A The An And But Or If When Then He She It They We You His Her Its Their Our Your This That These
Those There Here What Who Why How Where Which Not No Yes Mr Mrs Ms Sir Lady Lord Chapter One Two Three Even Still Just
After Before Once Now So As At In On Of For With From By To Up Down Out Over Under All Every Each Some Any My Me Him
Them Us Do Did Does Was Were Is Are Be Been Let Perhaps Maybe Only Then Yet Though Although Because While Until""".split())
_RUN = re.compile(r"(?<![A-Za-z'’])[A-Z][a-z]+(?:[ -][A-Z][a-z]+)*")
_SENT = re.compile(r"(?:^|[.!?…\"“”'‘’]\s*|\n\s*)$")


def new_name_candidates(g, text, min_count=2, limit=15):
    """Capitalised runs ('Wei Shan', 'Black River') that aren't known names. A run at a sentence start
    only counts if the same word also appears mid-sentence somewhere (so 'Then' / 'Lightning' are ignored)."""
    known = set()
    for e in g["entities"].values():
        for nm in (e["name"], *e.get("aliases", ())):
            known.update(nm.split())
    mid, runs = set(), []
    for m in _RUN.finditer(text):
        start = bool(_SENT.search(text[max(0, m.start() - 3):m.start()])) or m.start() == 0
        words_ = m.group(0).replace("-", " ").split()
        if not start:
            mid.update(words_)
        runs.append((words_, start))
    c = {}
    for words_, start in runs:
        while words_ and (words_[0] in _STOP or (start and len(words_) == 1 and words_[0] not in mid)):
            words_ = words_[1:]
            start = False
        if not words_ or all(w in known for w in words_):
            continue
        name = " ".join(words_)
        c[name] = c.get(name, 0) + 1
    return [(k, v) for k, v in sorted(c.items(), key=lambda kv: -kv[1]) if v >= min_count][:limit]


# ───────────── operations ─────────────

def _hist(e, ch, field, old, new, note=""):
    h = {"chapter": ch, "field": field, "new": new}
    if old not in (None, ""):
        h["old"] = old
    if note:
        h["note"] = note
    e["history"].append(h)


def apply(g, op, touched=None):
    """Apply one op to g in place. Returns a one-line description. Raises InkError if invalid."""
    k = op["op"]
    ch = op.get("chapter")
    E = g["entities"]
    T = touched if touched is not None else set()
    at = f" @ch{ch}" if ch else ""

    if k == "add":
        eid = op.get("id") or slug(op["name"])
        if eid in E:
            raise InkError(f"entity '{eid}' already exists")
        if op["type"] not in TYPES:
            raise InkError(f"type must be one of {', '.join(TYPES)}")
        status = op.get("status") or ("alive" if op["type"] == "character" else "active")
        _check_status(op["type"], status)
        E[eid] = {"id": eid, "type": op["type"], "name": op["name"], "aliases": list(op.get("aliases", [])),
                  "desc": op.get("desc", ""), "status": status, "fate": "", "attrs": dict(op.get("attrs", {})),
                  "tier": op.get("tier", 2), "first_seen": ch, "last_seen": ch,
                  "appearances": [ch] if ch else [], "history": [{"chapter": ch, "field": "created", "new": op.get("desc", "")}]}
        T.add(eid)
        extra = f" ({', '.join(f'{a}={b}' for a, b in op.get('attrs', {}).items())})" if op.get("attrs") else ""
        return f"+ {op['type']} {op['name']} [{eid}] {status}{extra}{at}"

    if k == "set":
        eid = resolve(g, op["id"])
        e = E[eid]
        parts = []
        for f, new in op.get("fields", {}).items():
            if f == "status":
                _check_status(e["type"], new)
            if f == "tier":
                new = int(new)
            old = e.get(f, "")
            if old == new:
                continue
            e[f] = new
            _hist(e, ch, f, old, new, op.get("note", ""))
            parts.append(f"{f}: {old or '∅'} → {new}")
        for a, new in op.get("attrs", {}).items():
            old = e["attrs"].get(a, "")
            if new in ("", "-"):
                if a not in e["attrs"]:
                    raise InkError(f"{e['name']} has no attribute '{a}'")
                del e["attrs"][a]
                new = "∅"
            else:
                e["attrs"][a] = new
            _hist(e, ch, f"attr.{a}", old, new, op.get("note", ""))
            parts.append(f"{a}: {old or '∅'} → {new}")
        if not parts:
            raise InkError(f"nothing changes for {e['name']}")
        T.add(eid)
        note = f"  ({op['note']})" if op.get("note") else ""
        return f"~ {e['name']}: " + "; ".join(parts) + at + note

    if k == "alias":
        eid = resolve(g, op["id"])
        for other in E.values():
            if other["id"] != eid and op["alias"].lower() in [x.lower() for x in (other["name"], *other["aliases"])]:
                raise InkError(f"'{op['alias']}' already names {other['name']}")
        if op["alias"] in E[eid]["aliases"]:
            raise InkError(f"{E[eid]['name']} already has alias '{op['alias']}'")
        E[eid]["aliases"].append(op["alias"])
        T.add(eid)
        return f"~ {E[eid]['name']}: alias + '{op['alias']}'"

    if k == "note":
        eid = resolve(g, op["id"])
        _hist(E[eid], ch, "note", None, op["text"])
        T.add(eid)
        return f"~ {E[eid]['name']}: note{at}: {op['text']}"

    if k == "link":
        a, b = resolve(g, op["a"]), resolve(g, op["b"])
        if a == b:
            raise InkError("cannot link an entity to itself")
        for r in g["relations"]:
            if r["a"] == a and r["b"] == b and r["rel"] == op["rel"] and r.get("until") is None:
                raise InkError(f"already active: {E[a]['name']} —{op['rel']}→ {E[b]['name']}")
        r = {"a": a, "b": b, "rel": op["rel"], "since": ch, "until": None}
        if op.get("note"):
            r["note"] = op["note"]
        g["relations"].append(r)
        T.update((a, b))
        return f"+ {E[a]['name']} —{op['rel']}→ {E[b]['name']}{at}"

    if k == "unlink":
        a, b = resolve(g, op["a"]), resolve(g, op["b"])
        for r in g["relations"]:
            if r["a"] == a and r["b"] == b and r["rel"] == op["rel"] and r.get("until") is None:
                r["until"] = ch
                if op.get("note"):
                    r["end_note"] = op["note"]
                T.update((a, b))
                return f"- {E[a]['name']} —{op['rel']}→ {E[b]['name']} ended{at}"
        raise InkError(f"no active relation {E[a]['name']} —{op['rel']}→ {E[b]['name']}")

    if k == "move":  # item/character changes holder: ends old holder link, adds new one
        item, to = resolve(g, op["item"]), resolve(g, op["to"])
        rel = op.get("rel", "owns")
        olds = [r for r in g["relations"] if r["b"] == item and r["rel"] == rel and r.get("until") is None]
        for r in olds:
            r["until"] = ch
            T.add(r["a"])
        g["relations"].append({"a": to, "b": item, "rel": rel, "since": ch, "until": None, **({"note": op["note"]} if op.get("note") else {})})
        T.update((item, to))
        frm = ", ".join(E[r["a"]]["name"] for r in olds) or "nobody"
        return f"⇄ {E[item]['name']}: {frm} → {E[to]['name']} ({rel}){at}"

    if k == "thread_open":
        tid = op.get("id") or slug(op["title"])
        if tid in g["threads"]:
            raise InkError(f"thread '{tid}' exists")
        if op.get("kind", "plot") not in THREAD_KINDS:
            raise InkError(f"kind must be one of {', '.join(THREAD_KINDS)}")
        inv = [resolve(g, x) for x in op.get("involves", [])]
        g["threads"][tid] = {"id": tid, "title": op["title"], "kind": op.get("kind", "plot"), "status": "open",
                             "planted": ch, "payoff_by": op.get("payoff_by"), "closed_in": None, "involves": inv,
                             "notes": [{"chapter": ch, "text": op["note"]}] if op.get("note") else []}
        T.add("t:" + tid)
        T.update(inv)
        pay = f", payoff by ch{op['payoff_by']}" if op.get("payoff_by") else ""
        return f"+ thread [{op.get('kind', 'plot')}] '{op['title']}'{at}{pay}"

    if k == "thread_note":
        tid = resolve_thread(g, op["id"])
        t = g["threads"][tid]
        t["notes"].append({"chapter": ch, "text": op["note"]})
        for x in op.get("involves", []):
            x = resolve(g, x)
            if x not in t["involves"]:
                t["involves"].append(x)
                T.add(x)
        T.add("t:" + tid)
        return f"~ thread '{t['title']}'{at}: {op['note']}"

    if k == "thread_close":
        tid = resolve_thread(g, op["id"])
        t = g["threads"][tid]
        if t["status"] != "open":
            raise InkError(f"thread '{t['title']}' is already {t['status']}")
        t["status"] = op.get("status", "closed")
        t["closed_in"] = ch
        if op.get("note"):
            t["notes"].append({"chapter": ch, "text": op["note"]})
        T.add("t:" + tid)
        return f"✓ thread '{t['title']}' {t['status']}{at}"

    if k == "event":
        base = eid = op.get("id") or slug(op["title"])
        i = 2
        while eid in g["events"]:
            eid, i = f"{base}-{i}", i + 1
        inv = [resolve(g, x) for x in op.get("involves", [])]
        g["events"][eid] = {"id": eid, "title": op["title"], "chapter": ch, "involves": inv,
                            "note": op.get("note", ""), "when": op.get("when", "")}
        T.add("e:" + eid)
        T.update(inv)
        names = f" ({', '.join(E[x]['name'] for x in inv)})" if inv else ""
        return f"+ event '{op['title']}'{at}{names}"

    raise InkError(f"unknown op '{k}'")


def _check_status(etype, status):
    allowed = CHAR_STATUS if etype == "character" else OTHER_STATUS
    if status not in allowed:
        raise InkError(f"status for {etype} must be one of {', '.join(allowed)}")
