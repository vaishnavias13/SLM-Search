"""Phase 3 check: tokenizer + model agree, parameter count, one forward pass.

Run:  python model/verify.py [tokenizer_dir]
"""
import math
import sys
from pathlib import Path

import torch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from model.initialize_model import build_model, count_parameters  # noqa: E402
from tokenizer.load import load_tokenizer  # noqa: E402

tdir = sys.argv[1] if len(sys.argv) > 1 else "tokenizer"
tok = load_tokenizer(Path(tdir) / "tokenizer.json")
model = build_model(tdir, seed=0).eval()
cfg = model.config

tok_vocab = tok.backend_tokenizer.get_vocab_size()
emb = model.get_input_embeddings().weight
print(f"Tokenizer vocab size : {tok_vocab}")
print(f"Model config vocab   : {cfg.vocab_size}")
print(f"Embedding rows       : {emb.shape[0]}")
assert tok_vocab == cfg.vocab_size == emb.shape[0], "vocab size mismatch!"
print("Vocab sizes match    : True")

assert (tok.pad_token_id, tok.bos_token_id, tok.eos_token_id) == (0, 2, 3), "unexpected special ids"
assert (cfg.pad_token_id, cfg.bos_token_id, cfg.eos_token_id) == (0, 2, 3), "config ids wrong"
print("Special ids          : pad=0 bos=2 eos=3 (asserted, read from tokenizer)")

total = count_parameters(model)
emb_params = emb.numel()
pos_params = model.transformer.wpe.weight.numel()
print(f"Total parameters     : {total:,} ({total / 1e6:.2f}M)")
print(f"  token embedding    : {emb_params:,} ({100 * emb_params / total:.1f}% of total; "
      f"shared with the output layer)")
print(f"  position embedding : {pos_params:,} ({100 * pos_params / total:.1f}%)")
print(f"  transformer blocks : {total - emb_params - pos_params:,}")
print(f"Layers/hidden/heads/context: {cfg.n_layer}/{cfg.n_embd}/{cfg.n_head}/{cfg.n_positions}")

text = "[BOS][SCHEMA] customers(id int, city text) [USER] Find customers from Pune [QUERY]"
ids = torch.tensor([tok.encode(text)])
with torch.no_grad():
    out = model(input_ids=ids, labels=ids)
assert out.logits.shape == (1, ids.shape[1], cfg.vocab_size)
expected = math.log(cfg.vocab_size)
loss = out.loss.item()
print(f"Forward pass: input {tuple(ids.shape)} -> logits {tuple(out.logits.shape)}")
print(f"Loss on random weights: {loss:.3f}   |   ln(vocab_size) = {expected:.3f}   "
      f"|   difference = {abs(loss - expected):.3f}")
assert math.isfinite(loss) and abs(loss - expected) < 1.0, "loss far from ln(vocab)!"
print("VERIFY PASSED")
