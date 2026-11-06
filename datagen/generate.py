"""Phase 4: build the synthetic database-search dataset.

Run:  python -m datagen.generate [--train 90000 --val 5000 --test 5000 --seed 1234]

Outputs (data/processed/):
  task_{train,validation,test}.txt    one training string per line: [BOS][SCHEMA] .. [USER] .. [QUERY] .. [EOS]
  task_{train,validation,test}.jsonl  separate fields (schema, question, plan, ...) for evaluation
  pretrain.txt                        plain text (schemas, SQL snippets, plans) from TRAIN schemas only
"""
import argparse
import collections
import json
import random
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.slm_search.validator import dump_plan, validate_plan  # noqa: E402
from datagen.catalog import TEST_DOMAINS, TRAIN_DOMAINS  # noqa: E402
from datagen.examples import Maker  # noqa: E402
from datagen.schema_gen import fingerprint, random_schema  # noqa: E402
from datagen.sqltext import plan_to_text  # noqa: E402
from tokenizer.load import load_tokenizer  # noqa: E402

OUT = Path("data/processed")
MAX_TOKENS = 512
PER_SCHEMA = 25
MONGO_FRACTION = 0.15


def values_in_question(plan, question):
    """Every string/number/date value in the plan must be written in the question exactly."""
    def leaves(c):
        if "or" in c:
            for x in c["or"]:
                yield from leaves(x)
        else:
            v = c["value"]
            yield from (v if isinstance(v, list) else [v])
    if plan.get("operation") != "search":
        return True
    for c in plan["filters"]:
        for v in leaves(c):
            if v is None or isinstance(v, bool):
                continue
            if not re.search(r"(?<![A-Za-z0-9])" + re.escape(str(v)) + r"(?![A-Za-z0-9])", question):
                return False
    return True


def table_words(schema):
    return {" ".join(t.words).lower() for t in schema.tables}


def build_split(name, n_target, domains, rng, tok, banned_fps, stats, seen_q):
    rows, fps, schemas_used = [], set(), 0
    batch = []
    while len(rows) < n_target:
        dialect = "mongo" if rng.random() < MONGO_FRACTION else "sql"
        schema = random_schema(random.Random(rng.random()), domains, dialect)
        fp = fingerprint(schema)
        if fp in banned_fps or fp in fps or not schema.allowed:
            stats["dropped_schema_dup"] += 1
            continue
        fps.add(fp)
        schemas_used += 1
        stext = schema.to_text()
        maker = Maker(random.Random(rng.random()), schema)
        cands = []
        for _ in range(PER_SCHEMA * 2):
            if len(cands) >= PER_SCHEMA:
                break
            ex = maker.make()
            if ex is None:
                stats["dropped_none"] += 1
                continue
            errs = validate_plan(ex["plan"], schema)
            if errs:
                stats["dropped_invalid"] += 1
                stats["invalid_examples"].append((ex["kind"], ex["question"], errs[:2], dump_plan(ex["plan"])[:200]))
                continue
            if not values_in_question(ex["plan"], ex["question"]):
                stats["dropped_value_not_in_question"] += 1
                continue
            key = (stext, ex["question"])
            if key in seen_q:
                stats["dropped_duplicate"] += 1
                continue
            seen_q.add(key)
            ex["plan_json"] = dump_plan(ex["plan"])
            ex["text"] = f"[BOS][SCHEMA] {stext} [USER] {ex['question']} [QUERY] {ex['plan_json']} [EOS]"
            cands.append(ex)
        lens = [len(e.ids) for e in tok.backend_tokenizer.encode_batch([c["text"] for c in cands])]
        for c, L in zip(cands, lens):
            if L > MAX_TOKENS:
                stats["dropped_too_long"] += 1
                continue
            if len(rows) >= n_target:
                break
            c.update(tokens=L, schema=stext, dialect=dialect, domain=schema.domain, split=name,
                     n_tables=len(schema.tables), n_joins=len(c["plan"].get("joins", [])),
                     schema_obj=schema)
            rows.append(c)
    return rows, fps


def write_split(rows, name):
    OUT.mkdir(parents=True, exist_ok=True)
    with open(OUT / f"task_{name}.txt", "w", encoding="utf-8", newline="\n") as ft, \
            open(OUT / f"task_{name}.jsonl", "w", encoding="utf-8", newline="\n") as fj:
        for i, r in enumerate(rows):
            ft.write(r["text"] + "\n")
            fj.write(json.dumps({
                "id": f"{name}-{i:06d}", "split": name, "kind": r["kind"], "dialect": r["dialect"],
                "domain": r["domain"], "style": r["style"], "schema": r["schema"], "question": r["question"],
                "plan": r["plan"], "plan_json": r["plan_json"], "tokens": r["tokens"],
            }, ensure_ascii=False) + "\n")


def write_pretrain(rows):
    """Plain text from TRAIN schemas only: schema line, then question / SQL snippet / plan triples."""
    by_schema = collections.OrderedDict()
    for r in rows:
        by_schema.setdefault(r["schema"], []).append(r)
    with open(OUT / "pretrain.txt", "w", encoding="utf-8", newline="\n") as f:
        for stext, exs in by_schema.items():
            f.write(f"Database schema: {stext}\n")
            for r in exs[:6]:
                f.write(f"Question: {r['question']}\n")
                snippet = plan_to_text(r["plan"])
                if snippet:
                    f.write(f"Query: {snippet}\n")
                f.write(f"Plan: {r['plan_json']}\n")
            f.write("\n")


def print_stats(name, rows):
    n = len(rows)
    kinds = collections.Counter(r["kind"] for r in rows)
    ops = collections.Counter(r["plan"]["operation"] for r in rows)
    print(f"\n=== {name}: {n:,} examples, {len({r['schema'] for r in rows}):,} schemas ===")
    print("  operation  :", {k: f"{v:,} ({100 * v / n:.1f}%)" for k, v in ops.items()})
    print("  kinds      :", dict(sorted(kinds.items())))
    print("  dialect    :", dict(collections.Counter(r["dialect"] for r in rows)))
    print("  tables/schema histogram:", dict(sorted(collections.Counter(r["n_tables"] for r in rows).items())))
    print("  joins histogram        :", dict(sorted(collections.Counter(r["n_joins"] for r in rows).items())))
    print(f"  avg tokens {sum(r['tokens'] for r in rows) / n:.1f} | max {max(r['tokens'] for r in rows)}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--train", type=int, default=90000)
    ap.add_argument("--val", type=int, default=5000)
    ap.add_argument("--test", type=int, default=5000)
    ap.add_argument("--seed", type=int, default=1234)
    ap.add_argument("--tokenizer", default="tokenizer/tokenizer.json")
    a = ap.parse_args()
    tok = load_tokenizer(a.tokenizer)
    rng = random.Random(a.seed)
    stats = collections.Counter()
    stats["invalid_examples"] = []
    seen_q = set()
    t0 = time.time()
    train, fp_tr = build_split("train", a.train, TRAIN_DOMAINS, rng, tok, set(), stats, seen_q)
    val, fp_va = build_split("validation", a.val, TRAIN_DOMAINS, rng, tok, fp_tr, stats, seen_q)
    test, fp_te = build_split("test", a.test, TEST_DOMAINS, rng, tok, fp_tr | fp_va, stats, seen_q)

    # ---------------- leakage checks (hard failures)
    assert not (fp_tr & fp_va) and not (fp_tr & fp_te) and not (fp_va & fp_te), "schema fingerprint leak"
    tw = lambda rows: set().union(*[table_words(r["schema_obj"]) for r in rows])  # noqa: E731
    from datagen.catalog import RESTRICTED_TABLES
    generic = set(RESTRICTED_TABLES)
    leak = (tw(test) & (tw(train) | tw(val))) - generic
    assert not leak, f"test table names also seen in train/val: {leak}"
    assert not ({r["domain"] for r in test} & {r["domain"] for r in train + val}), "domain leak"
    texts = [set(r["text"] for r in rows) for rows in (train, val, test)]
    assert not (texts[0] & texts[1]) and not (texts[0] & texts[2]) and not (texts[1] & texts[2]), "text leak"
    print("LEAKAGE CHECKS PASSED: no shared schemas, no shared domains (test), no shared table names (test), no shared examples")

    for name, rows in (("train", train), ("validation", val), ("test", test)):
        write_split(rows, name)
        print_stats(name, rows)
    write_pretrain(train)
    allr = train + val + test
    n = len(allr)
    non = sum(1 for r in allr if r["plan"]["operation"] in ("refuse", "clarify"))
    print(f"\nTOTAL {n:,} examples | refusal+clarify {100 * non / n:.1f}% | "
          f"avg tokens {sum(r['tokens'] for r in allr) / n:.1f} | {time.time() - t0:.0f}s")
    print("Drop counts:", {k: v for k, v in stats.items() if k != 'invalid_examples'})
    for ex in stats["invalid_examples"][:8]:
        print("  INVALID:", ex)
    print("Wrote files to", OUT.resolve())


if __name__ == "__main__":
    main()
