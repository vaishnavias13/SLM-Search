import collections
import random

from app.slm_search.schema import Schema
from app.slm_search.validator import validate_plan
from datagen.catalog import TEST_DOMAINS, TRAIN_DOMAINS
from datagen.examples import Maker
from datagen.generate import build_split, values_in_question
from datagen.schema_gen import fingerprint, random_schema
from tokenizer.load import load_tokenizer


def test_schema_sizes_and_text_roundtrip():
    rng = random.Random(0)
    sizes = collections.Counter()
    for i in range(400):
        s = random_schema(rng, TRAIN_DOMAINS if i % 2 else TEST_DOMAINS, "sql" if i % 5 else "mongo")
        assert 2 <= len(s.tables) <= 8
        assert all(3 <= len(t.columns) <= 12 for t in s.tables)
        assert s.allowed and set(s.allowed) <= {t.name for t in s.tables}
        assert Schema.from_text(s.to_text()).to_text() == s.to_text()
        sizes[len(s.tables)] += 1
    assert max(sizes) >= 6   # large schemas do occur


def test_test_domains_share_no_table_names_with_train():
    train = {t for d in TRAIN_DOMAINS.values() for t in d["tables"]}
    test = {t for d in TEST_DOMAINS.values() for t in d["tables"]}
    assert not (train & test)


def test_every_generated_example_is_valid_and_values_are_in_question():
    rng = random.Random(5)
    kinds = collections.Counter()
    for i in range(300):
        s = random_schema(rng, TRAIN_DOMAINS, "mongo" if i % 6 == 0 else "sql")
        m = Maker(random.Random(i), s)
        for _ in range(40):
            ex = m.make()
            if ex is None:
                continue
            assert validate_plan(ex["plan"], s) == [], (ex["question"], ex["plan"])
            assert values_in_question(ex["plan"], ex["question"]), (ex["question"], ex["plan"])
            kinds[ex["kind"]] += 1
    for k in ("search", "aggregate", "group_by", "join", "refuse:unknown_table", "refuse:unknown_column",
              "refuse:unauthorized_table", "refuse:write_operation", "clarify:ambiguous_column",
              "clarify:vague_request"):
        assert kinds[k] > 0, k


def test_values_check_catches_a_mismatch():
    plan = {"operation": "search", "filters": [{"column": "city", "operator": "equals", "value": "Pune"}]}
    assert values_in_question(plan, "customers where city is Pune")
    assert not values_in_question(plan, "customers where city is Punee")


def test_splits_have_no_leakage_and_test_uses_unseen_domains():
    tok = load_tokenizer()
    stats = collections.Counter()
    stats["invalid_examples"] = []
    seen = set()
    tr, fp_tr = build_split("train", 300, TRAIN_DOMAINS, random.Random(1), tok, set(), stats, seen)
    va, fp_va = build_split("validation", 60, TRAIN_DOMAINS, random.Random(2), tok, fp_tr, stats, seen)
    te, fp_te = build_split("test", 60, TEST_DOMAINS, random.Random(3), tok, fp_tr | fp_va, stats, seen)
    assert not (fp_tr & fp_va) and not (fp_tr & fp_te) and not (fp_va & fp_te)
    assert not ({r["domain"] for r in te} & {r["domain"] for r in tr + va})
    assert not ({r["text"] for r in tr} & {r["text"] for r in te})
    assert stats["dropped_invalid"] == 0
    assert all(r["tokens"] <= 512 for r in tr + va + te)
    assert all(r["text"].startswith("[BOS][SCHEMA] ") and r["text"].endswith(" [EOS]") for r in tr)
    assert all(" [USER] " in r["text"] and " [QUERY] " in r["text"] for r in tr)


def test_generation_is_deterministic():
    def run():
        s = random_schema(random.Random(9), TRAIN_DOMAINS, "sql")
        m = Maker(random.Random(9), s)
        return [(e["question"], e["plan"]) for e in (m.make() for _ in range(30)) if e]
    assert run() == run()
