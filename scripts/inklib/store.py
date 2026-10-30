"""Project storage: graph.json (source of truth), staged ops, history log, snapshots."""
import copy
import gzip
import json
from pathlib import Path

from . import ops as O
from .util import STATE, InkError, die, dump, now, read, write_atomic

SCHEMA = 2
DEFAULT_CONFIG = {"keep_snapshots": 25, "obsidian": True, "context_recent": 3, "rollup_every": 50, "pre_commit": ""}


def new_graph(title, genre="", pov="", tense="", words_min=1800, words_max=3000):
    return {
        "meta": {"title": title, "genre": genre, "pov": pov, "tense": tense,
                 "words_min": words_min, "words_max": words_max, "created": now(), "schema": SCHEMA},
        "config": dict(DEFAULT_CONFIG),
        "entities": {}, "relations": [], "threads": {}, "events": {},
        "chapters": {}, "arcs": {}, "position": {"last_chapter": 0},
    }


def migrate(g):
    g.setdefault("config", {})
    for k, v in DEFAULT_CONFIG.items():
        g["config"].setdefault(k, v)
    g["meta"]["schema"] = SCHEMA
    return g


def find_root(start=None):
    p = Path(start or Path.cwd()).resolve()
    for d in (p, *p.parents):
        if (d / STATE / "graph.json").exists():
            return d
    die("no inkgraph project here (run `ink init` or cd into the project)")


class Project:
    def __init__(self, root):
        self.root = Path(root)
        self.state = self.root / STATE
        self.gpath = self.state / "graph.json"
        self.ppath = self.state / "pending.json"
        self.hpath = self.state / "history.jsonl"
        self.snapdir = self.state / "snapshots"
        self.g = migrate(json.loads(read(self.gpath)))
        self.pending = json.loads(read(self.ppath)) if self.ppath.exists() else []
        self._trial = None
        self.quiet = False      # batch mode: don't print per op
        self.autosave = True    # batch mode: save once at the end
        self.staged = []        # descriptions staged by this process

    # paths
    def p(self, *parts):
        return self.root.joinpath(*parts)

    def rel(self, path):
        try:
            return str(Path(path).resolve().relative_to(self.root.resolve()))
        except ValueError:
            return str(path)

    @property
    def last(self):
        return self.g["position"]["last_chapter"]

    @property
    def cfg(self):
        return self.g["config"]

    # persistence
    def save(self):
        write_atomic(self.gpath, dump(self.g))

    def save_pending(self):
        write_atomic(self.ppath, dump(self.pending))

    # staging
    def trial(self):
        """Graph with all staged ops applied (cached for the life of this process)."""
        if self._trial is None:
            t = copy.deepcopy(self.g)
            for i, op in enumerate(self.pending, 1):
                try:
                    O.apply(t, op)
                except InkError as e:
                    die(f"staged op #{i} no longer applies: {e} — `ink discard {i}`")
            self._trial = t
        return self._trial

    def stage(self, op):
        desc = O.apply(self.trial(), op)  # validates; raises InkError
        self.pending.append(op)
        self.staged.append(f"#{len(self.pending)}: {desc}")
        if self.autosave:
            self.save_pending()
        if not self.quiet:
            print(f"staged #{len(self.pending)}: {desc}")
        return desc

    # history / snapshots
    def history(self):
        if not self.hpath.exists():
            return []
        return [json.loads(x) for x in read(self.hpath).splitlines() if x.strip()]

    def write_history(self, entries):
        write_atomic(self.hpath, "".join(json.dumps(e, ensure_ascii=False) + "\n" for e in entries))

    def snapshot(self, label):
        self.snapdir.mkdir(parents=True, exist_ok=True)
        stamp = now().replace(":", "").replace("-", "")
        snap = self.snapdir / f"{stamp}-{label}.json.gz"
        with open(self.gpath, "rb") as src, gzip.open(snap, "wb", compresslevel=6) as dst:
            dst.write(src.read())
        return snap

    def restore(self, name):
        snap = self.snapdir / name
        opener = gzip.open if name.endswith(".gz") else open
        with opener(snap, "rb") as f:
            data = f.read()
        write_atomic(self.gpath, data.decode("utf-8"))

    def prune_snapshots(self, history):
        keep = int(self.cfg.get("keep_snapshots", 25))
        live = {e["snapshot"] for e in history[-keep:]}
        for e in history[:-keep] if keep else history:
            if e.get("snapshot") and e["snapshot"] not in live:
                (self.snapdir / e["snapshot"]).unlink(missing_ok=True)
                e["snapshot"] = None
