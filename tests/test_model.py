import math
import re
from pathlib import Path

import torch

from model.initialize_model import build_model, count_parameters
from tokenizer.load import load_tokenizer


def test_vocab_and_special_ids_come_from_tokenizer():
    tok = load_tokenizer()
    m = build_model("tokenizer")
    assert m.config.vocab_size == tok.backend_tokenizer.get_vocab_size()
    assert m.get_input_embeddings().weight.shape[0] == m.config.vocab_size
    assert (m.config.pad_token_id, m.config.bos_token_id, m.config.eos_token_id) == (0, 2, 3)
    assert (m.config.n_layer, m.config.n_embd, m.config.n_head, m.config.n_positions) == (4, 256, 4, 512)


def test_build_model_follows_a_different_tokenizer_dir(tmp_path):
    # Train a tiny second tokenizer and check the model rebuilds to its vocab size.
    from tokenizer.train_tokenizer import train
    corpus = tmp_path / "c.txt"
    corpus.write_text("select name from users where age > 3\n" * 50, encoding="utf-8")
    t = train([corpus], vocab_size=400, out_path=tmp_path / "tokenizer.json")
    m = build_model(str(tmp_path))
    assert m.config.vocab_size == t.get_vocab_size() != build_model("tokenizer").config.vocab_size


def test_random_init_seed_behaviour():
    a, b, c = build_model(seed=1), build_model(seed=1), build_model(seed=2)
    w = lambda m: m.transformer.h[0].attn.c_attn.weight  # noqa: E731
    assert torch.equal(w(a), w(b))
    assert not torch.equal(w(a), w(c))


def test_forward_pass_and_random_loss_near_ln_vocab():
    m = build_model(seed=0).eval()
    ids = torch.randint(0, m.config.vocab_size, (2, 64))
    with torch.no_grad():
        out = m(input_ids=ids, labels=ids)
    assert out.logits.shape == (2, 64, m.config.vocab_size)
    assert abs(out.loss.item() - math.log(m.config.vocab_size)) < 1.0
    assert count_parameters(m) > 1_000_000


def test_source_never_loads_external_pretrained_models():
    """Only our own config/checkpoint dirs may be passed to from_pretrained."""
    for f in list(Path("model").glob("*.py")) + list(Path("training").glob("*.py")):
        for arg in re.findall(r"from_pretrained\(\s*[\"']([^\"']+)[\"']", f.read_text(encoding="utf-8")):
            assert arg.startswith("checkpoints"), f"{f}: suspicious from_pretrained({arg!r})"
