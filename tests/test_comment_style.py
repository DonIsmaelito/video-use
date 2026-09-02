"""guards the comment convention across every python file in the repo
each file opens with a module docstring and every def or class has one plain comment line above it
comments must not carry punctuation so they stay short and readable at a glance
"""

import ast
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKIP_DIRS = {".venv", "venv", "node_modules", "__pycache__", ".git", "media", "edit"}
PUNCTUATION = re.compile(r"[.,:;()\"'`]")
DEFINITION = re.compile(r"\s*(async def|def|class) \w")


# yield every python file in the repo that is not inside a skipped directory
def python_files():
    for path in ROOT.rglob("*.py"):
        if not any(part in SKIP_DIRS for part in path.relative_to(ROOT).parts):
            yield path


# return the problems found in one file as short strings
def audit(text):
    lines = text.splitlines()
    problems = []
    # the file opens with a docstring and not with a block of hash comments
    first = [line for line in lines[:6] if line.strip() and not line.startswith("#!")]
    if first and first[0].startswith("#"):
        problems.append("hash comment header should be a module docstring")
    try:
        if ast.get_docstring(ast.parse(text)) is None:
            problems.append("missing module docstring")
    except SyntaxError:
        problems.append("file does not parse")
    for index, line in enumerate(lines):
        if not DEFINITION.match(line):
            continue
        above = index - 1
        # decorators sit between the comment and the definition
        while above >= 0 and lines[above].strip().startswith("@"):
            above -= 1
        if above < 0 or not lines[above].strip().startswith("#"):
            problems.append(f"line {index + 1} has no comment above {line.strip()[:40]}")
            continue
        comment = lines[above].strip().lstrip("#").strip()
        if PUNCTUATION.search(comment):
            problems.append(f"line {above + 1} comment contains punctuation")
    return problems


# one test that scans the whole repo so a single failure lists every offending file
class CommentStyleTests(unittest.TestCase):
    # every python file must satisfy the header and per definition comment rules
    def test_every_python_file_follows_the_convention(self):
        failures = {}
        for path in python_files():
            problems = audit(path.read_text(encoding="utf-8"))
            if problems:
                failures[str(path.relative_to(ROOT))] = problems[:5]
        self.assertEqual(failures, {}, "comment convention violations")


if __name__ == "__main__":
    unittest.main()
