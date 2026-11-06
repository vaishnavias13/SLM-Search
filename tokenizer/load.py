"""Load our own trained tokenizer as a Hugging Face tokenizer object."""
from pathlib import Path

from transformers import PreTrainedTokenizerFast

TOKENIZER_PATH = Path(__file__).resolve().parent / "tokenizer.json"


def load_tokenizer(path=TOKENIZER_PATH):
    return PreTrainedTokenizerFast(
        tokenizer_file=str(path),
        pad_token="[PAD]",
        unk_token="[UNK]",
        bos_token="[BOS]",
        eos_token="[EOS]",
        additional_special_tokens=["[SCHEMA]", "[USER]", "[QUERY]"],
    )
