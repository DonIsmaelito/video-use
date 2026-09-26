"""Shared bits for the Jev experiments: dataset paths, timing, result writing."""
from __future__ import annotations

import json
import statistics
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
DATA = HERE / "data"
RESULTS = HERE / "results"
REPO = HERE.parents[1]
sys.path.insert(0, str(REPO))
from helpers.jev import Jev, choice, noul, answer_to_dict  # noqa: E402,F401


def read_jsonl(name: str) -> list[dict]:
    return [json.loads(l) for l in (DATA / name).open() if l.strip()]


def write_result(name: str, summary: dict, rows: list[dict], markdown: str) -> None:
    RESULTS.mkdir(exist_ok=True)
    (RESULTS / f"{name}.json").write_text(json.dumps({"summary": summary, "rows": rows}, indent=1, default=str))
    (RESULTS / f"{name}.md").write_text(markdown)
    print(markdown)


def stats(values: list[float]) -> dict:
    v = [x for x in values if x is not None]
    if not v:
        return {"n": 0}
    v.sort()
    return {"n": len(v), "median": round(statistics.median(v), 2), "mean": round(statistics.mean(v), 2), "p90": round(v[int(len(v) * 0.9) - 1 if len(v) > 1 else 0], 2), "min": round(v[0], 2), "max": round(v[-1], 2)}


def timed(fn):
    t0 = time.perf_counter()
    out = fn()
    return out, time.perf_counter() - t0


def clip(s: str, n: int) -> str:
    s = s or ""
    return s if len(s) <= n else s[: n // 2] + " … " + s[-n // 2 :]
