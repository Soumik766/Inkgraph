"""Argument parsing and dispatch, including `ink batch` (many staging commands, one call, all-or-nothing)."""
import argparse
import shlex
import sys

from . import commands as C
from .style import cmd_style
from .store import Project, find_root
from .util import InkError, THREAD_KINDS, TYPES

STAGING = {"add", "set", "kill", "alias", "note", "link", "unlink", "move", "thread", "event"}


class _Parser(argparse.ArgumentParser):
    def error(self, message):  # raise instead of exiting, so batch can report the line
        raise InkError(f"{self.prog}: {message}")


def build():
    ap = _Parser(prog="ink", description="inkgraph — story graph for long novels")
    ap.add_argument("--root", help="project folder (default: search upward from cwd)")
    sp = ap.add_subparsers(dest="cmd", required=True, parser_class=_Parser)

    def cmd(name, fn, help_):
        p = sp.add_parser(name, help=help_)
        p.set_defaults(fn=fn)
        return p

    def ch(p, required=False):
        p.add_argument("-c", "--chapter", type=int, required=required)

    p = sp.add_parser("init", help="create a project")
    p.set_defaults(fn=None)
    p.add_argument("dir"); p.add_argument("--title", required=True); p.add_argument("--genre")
    p.add_argument("--pov"); p.add_argument("--tense")
    p.add_argument("--words-min", type=int, default=1800); p.add_argument("--words-max", type=int, default=3000)
    p = cmd("config", C.config, "show or change settings (key=value …)"); p.add_argument("pairs", nargs="*")

    # staging
    p = cmd("add", C.add, "stage a new entity"); p.add_argument("type", choices=TYPES); p.add_argument("name")
    p.add_argument("--id"); p.add_argument("--aliases"); p.add_argument("--desc"); p.add_argument("--status")
    p.add_argument("--tier", type=int, choices=(1, 2, 3), default=2, help="1 main · 2 supporting · 3 minor")
    p.add_argument("--attr", action="append", metavar="K=V"); ch(p)
    p = cmd("set", C.set_, "stage changes to an entity"); p.add_argument("entity")
    p.add_argument("--status"); p.add_argument("--fate"); p.add_argument("--desc"); p.add_argument("--name")
    p.add_argument("--tier", type=int, choices=(1, 2, 3))
    p.add_argument("--attr", action="append", metavar="K=V", help="K=- removes"); p.add_argument("--note"); ch(p, True)
    p = cmd("kill", C.kill, "stage a death with its fate"); p.add_argument("entity")
    p.add_argument("--fate", required=True); p.add_argument("--note"); ch(p, True)
    p = cmd("alias", C.alias, "stage an alias"); p.add_argument("entity"); p.add_argument("alias")
    p = cmd("note", C.note, "stage a history fact"); p.add_argument("entity"); p.add_argument("text"); ch(p, True)
    p = cmd("link", C.link, "stage relation A —rel→ B"); p.add_argument("a"); p.add_argument("rel"); p.add_argument("b")
    p.add_argument("--mutual", action="store_true"); p.add_argument("--note"); ch(p)
    p = cmd("unlink", C.unlink, "stage end of a relation"); p.add_argument("a"); p.add_argument("rel"); p.add_argument("b")
    p.add_argument("--note"); ch(p, True)
    p = cmd("move", C.move, "stage an item changing hands"); p.add_argument("item"); p.add_argument("to")
    p.add_argument("--rel", default="owns"); p.add_argument("--note"); ch(p, True)
    p = cmd("thread", C.thread, "stage thread open/note/close/abandon")
    p.add_argument("action", choices=("open", "note", "close", "abandon")); p.add_argument("ref", help="title (open) or id")
    p.add_argument("text", nargs="?"); p.add_argument("--note"); p.add_argument("--kind", default="plot", choices=THREAD_KINDS)
    p.add_argument("--payoff-by", type=int); p.add_argument("--involves"); ch(p)
    p = cmd("event", C.event, "stage a turning point"); p.add_argument("title"); p.add_argument("--involves")
    p.add_argument("--note"); p.add_argument("--when"); ch(p)
    p = cmd("batch", run_batch, "stage many commands from a file/stdin, all-or-nothing")
    p.add_argument("file", nargs="?", default="-")

    # review
    p = cmd("diff", C.diff, "show staged changes, detections, blockers"); ch(p)
    p = cmd("commit", C.commit, "apply staged changes (after author approval)"); ch(p)
    p.add_argument("--setup", action="store_true"); p.add_argument("--yes", action="store_true")
    p = cmd("discard", C.discard, "drop all staged ops, or op N"); p.add_argument("index", type=int, nargs="?")
    p = cmd("undo", C.undo, "revert the last commit"); p.add_argument("--yes", action="store_true")

    # reading
    p = cmd("context", C.context, "retrieval bundle for writing a chapter"); ch(p)
    p.add_argument("--involves"); p.add_argument("--recent", type=int); p.add_argument("--max-back", type=int, default=6)
    p.add_argument("--max-chars", type=int, default=0, help="trim low-priority sections to fit"); p.add_argument("--outline", action="store_true")
    p = cmd("check", C.check, "continuity-check a draft"); p.add_argument("file", nargs="?"); ch(p)
    p = cmd("find", C.find, "search the graph"); p.add_argument("query")
    p.add_argument("--text", action="store_true", help="also search summaries"); p.add_argument("--limit", type=int, default=40)
    p = cmd("show", C.show, "full entity card"); p.add_argument("entity")
    p = cmd("threads", C.threads, "list threads"); p.add_argument("--all", action="store_true")
    p = cmd("list", C.list_, "list entities"); p.add_argument("--type", choices=TYPES); p.add_argument("--status")
    p.add_argument("--tier", type=int, choices=(1, 2, 3))
    p = cmd("style", cmd_style, "prose fingerprint of samples, or compare a draft to it"); p.add_argument("file", nargs="?"); ch(p)
    cmd("status", C.status, "project overview")
    cmd("doctor", C.doctor, "integrity + health checks")
    p = cmd("rollup", C.rollup, "print summaries for an arc"); p.add_argument("--from", dest="from_", type=int, required=True)
    p.add_argument("--to", type=int, required=True)
    p = cmd("arc", C.arc, "register an arc"); p.add_argument("number", type=int); p.add_argument("--title", required=True)
    p.add_argument("--from", dest="from_", type=int, required=True); p.add_argument("--to", type=int)

    # views
    cmd("render", C.render, "rebuild Obsidian notes in graph/")
    p = cmd("graph", C.graph, "write the offline story map (story-map.html)"); p.add_argument("--out")
    p.add_argument("--no-threads", action="store_true")
    p = cmd("export", C.export, "export final chapters"); p.add_argument("--format", choices=("docx", "txt", "md"), default="docx")
    p.add_argument("--from", dest="from_", type=int); p.add_argument("--to", type=int); p.add_argument("--caps", action="store_true")
    return ap


def run_batch(a, P):
    """One ink staging command per line (leading `ink` optional, '#' comments allowed).
    Lines are validated in order against the evolving graph; if any fails, nothing is staged."""
    src = sys.stdin.read() if a.file == "-" else open(a.file, encoding="utf-8").read()
    parser = build()
    P.quiet, P.autosave = True, False
    for no, line in enumerate(src.splitlines(), 1):
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        try:
            argv = shlex.split(line)
            if argv and argv[0] == "ink":
                argv = argv[1:]
            if not argv or argv[0] not in STAGING:
                raise InkError(f"only staging commands are allowed ({', '.join(sorted(STAGING))})")
            sub = parser.parse_args(argv)
            sub.fn(sub, P)
        except (InkError, ValueError) as e:
            raise InkError(f"batch line {no}: {line}\n  {e}\n  nothing staged")
    P.save_pending()
    print(f"staged {len(P.staged)} op(s):")
    print("\n".join("  " + d for d in P.staged))


def main(argv=None):
    try:
        a = build().parse_args(argv)
        if a.cmd == "init":
            return C.init(a)
        P = Project(find_root(a.root))
        a.fn(a, P)
    except InkError as e:
        print(f"error: {e}", file=sys.stderr)
        sys.exit(1)
    except BrokenPipeError:
        pass
