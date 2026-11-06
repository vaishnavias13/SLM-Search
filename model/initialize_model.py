"""Create a brand-new model with RANDOM weights.

IMPORTANT:
  * GPT2LMHeadModel(config) builds a fresh random network. Nothing is downloaded.
  * We never load any external pretrained model.
  * Later phases may load OUR OWN checkpoints (written by our training scripts) -
    that is different and allowed.

Rebuild after retraining the tokenizer, in one command:
    python model/initialize_model.py tokenizer
"""
import sys
from pathlib import Path

import torch
from transformers import GPT2LMHeadModel

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from model.config import build_config  # noqa: E402
from tokenizer.load import load_tokenizer  # noqa: E402

INIT_DIR = Path("checkpoints/initial-model")


def build_model(tokenizer_dir="tokenizer", seed=None) -> GPT2LMHeadModel:
    """Random-weight GPT-2 whose vocab size and special ids come from the saved tokenizer."""
    tokenizer = load_tokenizer(Path(tokenizer_dir) / "tokenizer.json")
    config = build_config(tokenizer)
    if seed is not None:
        torch.manual_seed(seed)
    return GPT2LMHeadModel(config)  # random init


def count_parameters(model) -> int:
    return sum(p.numel() for p in model.parameters())  # tied weights count once


if __name__ == "__main__":
    tdir = sys.argv[1] if len(sys.argv) > 1 else "tokenizer"
    model = build_model(tdir, seed=42)
    n = count_parameters(model)
    model.config.save_pretrained("checkpoints/config")
    model.save_pretrained(INIT_DIR)
    print(f"Model initialized (random weights, nothing downloaded) from tokenizer in '{tdir}'.")
    print(f"vocab_size={model.config.vocab_size}  parameters={n:,} ({n / 1e6:.2f}M)")
    print("Saved our own random-init model to:", INIT_DIR)
