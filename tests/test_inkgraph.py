"""End-to-end tests for the ink CLI. Run: python3 -m unittest discover -s tests"""
import contextlib
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
from inklib.cli import main  # noqa: E402


class Proj:
    def __init__(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name) / "novel"
        self.run("init", str(self.root), "--title", "Test Saga", "--words-min", "10", "--words-max", "500")

    def run(self, *argv, stdin=None, ok=True):
        buf, err = io.StringIO(), io.StringIO()
        old = sys.stdin
        sys.stdin = io.StringIO(stdin or "")
        code = 0
        try:
            with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(err):
                main(list(argv) if argv[0] == "init" else ["--root", str(self.root), *argv])
        except SystemExit as e:
            code = e.code or 0
        finally:
            sys.stdin = old
        if ok and code:
            raise AssertionError(f"ink {argv} exited {code}: {buf.getvalue()}{err.getvalue()}")
        return code, buf.getvalue() + err.getvalue()

    def out(self, *argv, **kw):
        return self.run(*argv, **kw)[1]

    def chapter(self, n, text, summary="- something happens"):
        (self.root / "chapters/draft" / f"ch-{n:04d}.md").write_text(f"# Chapter {n}: T{n}\n\n{text}\n")
        (self.root / "summaries/chapters" / f"ch-{n:04d}.md").write_text(summary + "\n")

    def graph(self):
        return json.loads((self.root / ".inkgraph/graph.json").read_text())


SETUP = """
add character "Lin Feng" --tier 1 --aliases Feng --attr realm=Qi3 -c 1
add character "Elder Mo" -c 1
add item "Jade Pendant" -c 1
add location "Black River" -c 1
link "Lin Feng" owns "Jade Pendant" -c 1
thread open "Pendant origin" --kind foreshadow --involves "Lin Feng" --payoff-by 5 -c 1
"""


class TestWorkflow(unittest.TestCase):
    def setUp(self):
        self.p = Proj()
        self.p.run("batch", stdin=SETUP)
        self.p.run("commit", "--setup", "--yes")

    def tearDown(self):
        self.p.tmp.cleanup()

    def test_batch_is_all_or_nothing(self):
        code, out = self.p.run("batch", stdin='add character "Su Yan" -c 1\nkill "Nobody" --fate x -c 1', ok=False)
        self.assertEqual(code, 1)
        self.assertIn("batch line 2", out)
        self.assertIn("0 staged op(s)", self.p.out("diff"))

    def test_commit_requires_summary_and_approval(self):
        (self.p.root / "chapters/draft/ch-0001.md").write_text("# Chapter 1\n\nLin Feng walks.\n")
        code, out = self.p.run("diff", "-c", "1", ok=False)
        self.assertEqual(code, 2)
        self.assertIn("missing chapter summary", out)
        self.p.chapter(1, "Lin Feng walks to the black river with the jade pendant.")
        code, out = self.p.run("commit", "-c", "1", ok=False)  # stdin is not a tty → refuses
        self.assertEqual(code, 1)
        self.assertIn("approval", out)
        self.p.run("commit", "-c", "1", "--yes")
        g = self.p.graph()
        self.assertEqual(g["position"]["last_chapter"], 1)
        self.assertIn(1, g["entities"]["jade-pendant"]["appearances"])  # case-insensitive item match
        self.assertIn(1, g["entities"]["black-river"]["appearances"])
        self.assertTrue((self.p.root / "chapters/final/ch-0001.md").exists())

    def test_character_names_need_capitals(self):
        self.p.run("add", "character", "Hope")
        self.p.chapter(1, "There was no hope left for Lin Feng.")
        self.p.run("commit", "-c", "1", "--yes")
        self.assertNotIn(1, self.p.graph()["entities"]["hope"]["appearances"])
        self.p.chapter(2, "Hope ran to Lin Feng.")
        self.p.run("commit", "-c", "2", "--yes")
        self.assertIn(2, self.p.graph()["entities"]["hope"]["appearances"])

    def test_death_check_and_context(self):
        self.p.chapter(1, "Elder Mo dies. Lin Feng watches.")
        self.p.run("kill", "Elder Mo", "--fate", "poisoned", "-c", "1")
        self.p.run("commit", "-c", "1", "--yes")
        self.p.chapter(2, "Elder Mo smiled at Lin Feng. Wei Shan laughed. Lin Feng saw Wei Shan go.")
        out = self.p.out("check", "-c", "2")
        self.assertIn("Elder Mo is dead", out)
        self.assertIn("Wei Shan", out)  # new-name detection
        ctx = self.p.out("context", "--involves", "Lin Feng,Elder Mo")
        self.assertIn("GONE: Elder Mo", ctx)
        self.assertIn("Pendant origin", ctx)
        self.assertIn("held items: Jade Pendant", ctx)

    def test_move_and_doctor(self):
        self.p.run("add", "character", "Old Hua", "-c", "1")
        self.p.run("move", "Jade Pendant", "Old Hua", "-c", "1")
        self.p.chapter(1, "Old Hua takes the pendant from Lin Feng.")
        self.p.run("commit", "-c", "1", "--yes")
        rels = [r for r in self.p.graph()["relations"] if r["b"] == "jade-pendant"]
        self.assertEqual([r["until"] for r in rels if r["a"] == "lin-feng"], [1])
        self.assertEqual([r["until"] for r in rels if r["a"] == "old-hua"], [None])
        self.assertIn("healthy", self.p.out("doctor"))

    def test_undo_restores_everything(self):
        self.p.chapter(1, "Lin Feng breaks through.")
        self.p.run("set", "Lin Feng", "--attr", "realm=Foundation1", "-c", "1")
        self.p.run("commit", "-c", "1", "--yes")
        self.p.run("undo", "--yes")
        g = self.p.graph()
        self.assertEqual(g["entities"]["lin-feng"]["attrs"]["realm"], "Qi3")
        self.assertTrue((self.p.root / "chapters/draft/ch-0001.md").exists())
        self.assertIn("realm", self.p.out("diff", "-c", "1"))  # ops re-staged
        self.p.run("commit", "-c", "1", "--yes")
        self.assertEqual(self.p.graph()["entities"]["lin-feng"]["attrs"]["realm"], "Foundation1")

    def test_validation_errors(self):
        for argv, msg in [(("link", "Lin Feng", "owns", "Jade Pendant", "-c", "1"), "already active"),
                          (("set", "Lin Feng", "--status", "asleep", "-c", "1"), "status for character"),
                          (("add", "character", "Lin Feng"), "already exists"),
                          (("alias", "Elder Mo", "Feng"), "already names"),
                          (("thread", "close", "nope", "-c", "1"), "unknown thread")]:
            code, out = self.p.run(*argv, ok=False)
            self.assertEqual(code, 1, argv)
            self.assertIn(msg, out)

    def test_views_and_export(self):
        self.p.chapter(1, "Lin Feng *walks*. **Bold** move.")
        self.p.run("commit", "-c", "1", "--yes")
        self.p.run("graph")
        html = (self.p.root / "story-map.html").read_text()
        self.assertNotIn("http://", html.replace("http://www.w3.org", ""))  # fully offline
        self.assertNotIn("https://", html)
        self.assertIn('"Lin Feng"', html)
        self.assertTrue((self.p.root / "graph/characters/lin-feng.md").exists())
        self.p.run("export", "--format", "txt")
        txt = next((self.p.root / "export").glob("*.txt")).read_text()
        self.assertIn("Lin Feng walks. Bold move.", txt)

    def test_style_fingerprint(self):
        (self.p.root / "bible/samples/s1.md").write_text('Rain fell. "You came," she said.\n\n"I did." He sat.\n')
        self.p.chapter(1, "The air was thick — a palpable tapestry; it was a testament to everything.")
        out = self.p.out("style", "-c", "1")
        self.assertIn("AI-tell phrases", out)
        self.assertIn("em_dash_per_k", out)

    def test_refuses_project_inside_skill_folder(self):
        inside = Path(__file__).resolve().parent.parent / "my-novel"
        code, out = self.p.run("init", str(inside), "--title", "X", ok=False)
        self.assertEqual(code, 1)
        self.assertIn("refusing", out)
        self.assertFalse(inside.exists())

    def test_snapshot_pruning(self):
        self.p.run("config", "keep_snapshots=2")
        for n in range(1, 5):
            self.p.chapter(n, "Lin Feng.")
            self.p.run("commit", "-c", str(n), "--yes")
        self.assertEqual(len(list((self.p.root / ".inkgraph/snapshots").glob("*.gz"))), 2)


if __name__ == "__main__":
    unittest.main()
