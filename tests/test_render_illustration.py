import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from helpers import render_illustration as ri


class ParserTests(unittest.TestCase):
    def test_parses_both_engines(self):
        parser = ri.build_parser()
        cetz = parser.parse_args(["cetz", "fig.typ", "-o", "fig.svg"])
        self.assertEqual((cetz.engine, cetz.output.name), ("cetz", "fig.svg"))
        penrose = parser.parse_args(["penrose", "d.trio.json", "-o", "d.svg", "--variation", "seed1"])
        self.assertEqual((penrose.engine, penrose.variation), ("penrose", "seed1"))

    def test_requires_an_engine(self):
        with self.assertRaises(SystemExit):
            ri.build_parser().parse_args(["fig.typ", "-o", "fig.svg"])


class CetzTests(unittest.TestCase):
    def test_rejects_wrong_suffixes(self):
        with self.assertRaises(ValueError):
            ri.render_cetz(Path("fig.tex"), Path("fig.svg"))
        with self.assertRaises(ValueError):
            ri.render_cetz(Path("fig.typ"), Path("fig.mp4"))

    def test_explains_missing_typst(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "fig.typ"
            source.write_text("#circle()")
            with patch.object(ri.shutil, "which", return_value=None):
                with self.assertRaisesRegex(RuntimeError, "Typst CLI"):
                    ri.render_cetz(source, Path(tmp) / "fig.svg")


class PenroseTests(unittest.TestCase):
    def test_rejects_wrong_suffixes(self):
        with self.assertRaises(ValueError):
            ri.render_penrose(Path("d.json"), Path("d.svg"), variation=None, dump_steps=False, cache_root=Path("."))
        with self.assertRaises(ValueError):
            ri.render_penrose(Path("d.trio.json"), Path("d.png"), variation=None, dump_steps=False, cache_root=Path("."))

    def test_explains_missing_node(self):
        with tempfile.TemporaryDirectory() as tmp:
            with patch.object(ri.shutil, "which", return_value=None):
                with self.assertRaisesRegex(RuntimeError, "Node.js and npm"):
                    ri.ensure_roger(Path(tmp))

    def test_tool_cache_honours_env(self):
        with patch.dict(ri.os.environ, {"VIDEO_USE_TOOL_CACHE": "/tmp/vu-cache"}):
            self.assertEqual(ri.default_tool_cache(), Path("/tmp/vu-cache").resolve())


if __name__ == "__main__":
    unittest.main()
