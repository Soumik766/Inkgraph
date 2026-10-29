"""Small shared helpers: errors, text, ids, filenames."""
import datetime as dt
import json
import os
import re
import sys
from pathlib import Path

STATE = ".inkgraph"
TYPES = ("character", "location", "faction", "item", "power", "concept")
CHAR_STATUS = ("alive", "dead", "missing", "unknown", "sealed", "transformed")
OTHER_STATUS = ("active", "destroyed", "lost", "dormant", "unknown")
GONE = {"dead", "destroyed", "lost"}
HOLD_RELS = {"owns", "wields", "carries", "has", "holds"}
THREAD_KINDS = ("plot", "foreshadow", "mystery", "promise", "romance", "rivalry", "setup")

_META_RX = re.compile(r"\A---\n.*?\n---\n", re.S)
_COMMENT_RX = re.compile(r"<!--.*?-->", re.S)
_WORD_RX = re.compile(r"\S+")


class InkError(Exception):
    """User-facing error. CLI prints it and exits 1."""


def die(msg):
    raise InkError(msg)


def now():
    return dt.datetime.now().isoformat(timespec="seconds")


def slug(name):
    s = re.sub(r"[^a-z0-9]+", "-", name.strip().lower()).strip("-")
    return s or "untitled"


def chname(n):
    return f"ch-{int(n):04d}.md"


def chnum(path):
    return int(Path(path).stem[3:])


def strip_meta(text):
    return _COMMENT_RX.sub("", _META_RX.sub("", text))


def words(text):
    return len(_WORD_RX.findall(strip_meta(text)))


def read(path):
    return Path(path).read_text(encoding="utf-8")


def write_atomic(path, text):
    """Write via temp file + rename so a crash never leaves a half-written file."""
    path = Path(path)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    os.replace(tmp, path)


def dump(obj):
    return json.dumps(obj, ensure_ascii=False, indent=1, separators=(",", ":"))


def parse_kv(pairs):
    out = {}
    for p in pairs or []:
        if "=" not in p:
            die(f"expected key=value, got '{p}'")
        k, v = p.split("=", 1)
        out[k.strip()] = v.strip()
    return out


def csv(s):
    return [x.strip() for x in s.split(",") if x.strip()] if s else []


def out(*lines):
    if lines:
        sys.stdout.write("\n".join(lines) + "\n")
