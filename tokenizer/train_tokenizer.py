"""Phase 2: train our own byte-level BPE tokenizer.

Simple idea: text is first cut into raw bytes (256 possible values), then the trainer
repeatedly merges the most common neighbouring pieces into new, longer "words" until
the vocabulary is full. Because every byte is in the starting alphabet, ANY text can be
encoded and [UNK] should never appear.

Run:  python tokenizer/train_tokenizer.py [corpus_file ...]
"""
import sys
from pathlib import Path

from tokenizers import Tokenizer
from tokenizers.decoders import ByteLevel as ByteLevelDecoder
from tokenizers.models import BPE
from tokenizers.pre_tokenizers import ByteLevel
from tokenizers.trainers import BpeTrainer

# Exactly these 7 special tokens, in this order (so ids are 0..6).
SPECIAL_TOKENS = ["[PAD]", "[UNK]", "[BOS]", "[EOS]", "[SCHEMA]", "[USER]", "[QUERY]"]
VOCAB_SIZE = 16000
OUT_PATH = Path("tokenizer/tokenizer.json")


def train(files, vocab_size=VOCAB_SIZE, out_path=OUT_PATH):
    tokenizer = Tokenizer(BPE(unk_token="[UNK]"))
    tokenizer.pre_tokenizer = ByteLevel(add_prefix_space=False)
    tokenizer.decoder = ByteLevelDecoder()
    trainer = BpeTrainer(
        vocab_size=vocab_size,
        min_frequency=2,
        special_tokens=SPECIAL_TOKENS,
        initial_alphabet=ByteLevel.alphabet(),  # all 256 byte symbols
    )
    tokenizer.train([str(f) for f in files], trainer)
    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    tokenizer.save(str(out_path))
    return tokenizer


if __name__ == "__main__":
    files = sys.argv[1:] or ["data/raw/starter_corpus.txt"]
    tok = train(files)
    print("Custom tokenizer trained successfully!")
    print("Corpus files:", files)
    # The model's vocab_size must come from this number, not from a guess.
    print("Vocabulary size (tokenizer.get_vocab_size()):", tok.get_vocab_size())
    print("Saved to:", OUT_PATH)
