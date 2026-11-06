"""Model configuration (the "blueprint" of the network).

The vocabulary size is NOT typed by hand: it is read from our trained tokenizer so the
model and tokenizer can never disagree.
"""
import sys
from pathlib import Path

from transformers import GPT2Config

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tokenizer.load import load_tokenizer  # noqa: E402

CONFIG_DIR = Path("checkpoints/config")


def build_config(tokenizer=None) -> GPT2Config:
    tokenizer = tokenizer or load_tokenizer()
    return GPT2Config(
        vocab_size=tokenizer.backend_tokenizer.get_vocab_size(),  # from the tokenizer
        n_positions=512,      # context length: the model sees up to 512 tokens
        n_embd=256,           # hidden size
        n_layer=4,            # transformer blocks
        n_head=4,             # attention heads (256 / 4 = 64 per head)
        bos_token_id=tokenizer.bos_token_id,
        eos_token_id=tokenizer.eos_token_id,
        pad_token_id=tokenizer.pad_token_id,
        activation_function="gelu_new",
        resid_pdrop=0.1,
        embd_pdrop=0.1,
        attn_pdrop=0.1,
    )


if __name__ == "__main__":
    cfg = build_config()
    cfg.save_pretrained(CONFIG_DIR)
    print("Transformer configuration created! vocab_size =", cfg.vocab_size)
    print("Saved to:", CONFIG_DIR)
