"""Show 10 random samples (>=2 joins, >=2 refusals, >=1 clarify, >=1 MongoDB) for human checking.

Run: python scripts/show_samples.py [train|validation|test] [seed]
"""
import json
import random
import sys
from pathlib import Path

split = sys.argv[1] if len(sys.argv) > 1 else "train"
rng = random.Random(int(sys.argv[2]) if len(sys.argv) > 2 else 7)
rows = [json.loads(line) for line in open(Path("data/processed") / f"task_{split}.jsonl", encoding="utf-8")]


def pick(pred, k, taken):
    pool = [r for r in rows if pred(r) and r["id"] not in taken]
    chosen = rng.sample(pool, k)
    taken.update(r["id"] for r in chosen)
    return chosen


taken, picks = set(), []
picks += pick(lambda r: r["kind"] == "join", 2, taken)
picks += pick(lambda r: r["kind"].startswith("refuse"), 2, taken)
picks += pick(lambda r: r["kind"].startswith("clarify"), 1, taken)
picks += pick(lambda r: r["dialect"] == "mongo" and r["plan"]["operation"] == "search", 1, taken)
picks += pick(lambda r: r["kind"] in ("aggregate", "group_by"), 1, taken)
picks += pick(lambda r: r["kind"] == "search" and r["dialect"] == "sql", 3, taken)
rng.shuffle(picks)

for i, r in enumerate(picks, 1):
    head, allowed, tables = r["schema"].split(" | ", 2)
    print("=" * 100)
    print(f"SAMPLE {i}   [{r['kind']}]   dialect={r['dialect']}   domain={r['domain']}")
    print(f"  {head} | {allowed}")
    for t in tables.split(" ; "):
        print("    ", t)
    print("  QUESTION:", r["question"])
    print("  PLAN    :", r["plan_json"])
