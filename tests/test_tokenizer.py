from tokenizer.load import load_tokenizer

SPECIALS = ["[PAD]", "[UNK]", "[BOS]", "[EOS]", "[SCHEMA]", "[USER]", "[QUERY]"]


def test_special_tokens_are_first_seven_in_order():
    tok = load_tokenizer()
    assert [tok.convert_tokens_to_ids(t) for t in SPECIALS] == list(range(7))


def test_vocab_size_matches_and_not_above_16000():
    tok = load_tokenizer()
    assert len(tok) == tok.backend_tokenizer.get_vocab_size()
    assert len(tok) <= 16000


def test_no_unk_on_representative_and_weird_text():
    tok = load_tokenizer()
    texts = [
        'SELECT * FROM t WHERE a = 1;', '{"a": [1, 2, {"b": null}]}', "café 東京 🙂 \t\n",
        'db.x.find({"$gt": 3})', bytes(range(32, 127)).decode("ascii"),
    ]
    for t in texts:
        assert tok.unk_token_id not in tok.encode(t), t


def test_roundtrip_and_special_tokens_are_single_ids():
    tok = load_tokenizer()
    s = "[BOS][SCHEMA] a(id int) [USER] hi [QUERY] {} [EOS]"
    ids = tok.encode(s)
    assert tok.decode(ids) == s
    for t in SPECIALS[2:]:
        assert ids.count(tok.convert_tokens_to_ids(t)) == 1
