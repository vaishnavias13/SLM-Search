"""Show how the tokenizer splits a sample, and prove there is no [UNK]."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tokenizer.load import load_tokenizer  # noqa: E402

tok = load_tokenizer()
SAMPLES = [
    '[BOS][SCHEMA] customers(id int, name text, city text) [USER] Find customers from Bengaluru '
    '[QUERY] {"operation": "search", "table": "customers", "filters": [{"column": "city", '
    '"operator": "equals", "value": "Bengaluru"}], "limit": 100} [EOS]',
    "SELECT name FROM orders WHERE total > 1000 ORDER BY total DESC LIMIT 5;",
    'db.products.find({"price": {"$gt": 1000}})',
    "Unicode and odd text: café, 東京, naïve, emoji 🙂, tab\tand newline\n!",
]
unk_id = tok.unk_token_id
print("Vocab size:", len(tok), "| special token ids:",
      {t: tok.convert_tokens_to_ids(t) for t in ["[PAD]", "[UNK]", "[BOS]", "[EOS]",
                                                  "[SCHEMA]", "[USER]", "[QUERY]"]})
bad = 0
for s in SAMPLES:
    ids = tok.encode(s)
    n_unk = ids.count(unk_id)
    bad += n_unk
    print("\nTEXT  :", repr(s))
    print("TOKENS:", tok.convert_ids_to_tokens(ids))
    print(f"COUNT : {len(ids)} tokens, [UNK] count = {n_unk}")
    print("ROUNDTRIP OK:", tok.decode(ids) == s)
print("\nTOTAL [UNK] across samples:", bad)
sys.exit(1 if bad else 0)
