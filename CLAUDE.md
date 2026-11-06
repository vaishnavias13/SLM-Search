# Universal Database Search SLM — Project Rules

Spec: `Universal_Database_Search_SLM_Option_B_Guide.docx` (kept in the user's Downloads folder).

## What this project is
A small GPT-2-style decoder-only language model with a CUSTOM tokenizer and RANDOMLY
INITIALIZED weights. It turns a natural-language question + a database schema into a
JSON query plan. A deterministic validation layer then runs the plan safely through a
FastAPI service.

## Working style (the user is a complete beginner)
- Explain every step in simple words.
- Work ONE PHASE AT A TIME. At the start of a phase, show a short plan. At the end, show the
  "done when" result and STOP. Wait for the user's approval before the next phase.
- Test and run everything before saying it is done. Show the real terminal output.
- Never claim a feature works without testing it. Do not silently skip tests.
- Record failed tests and explain how they were fixed (keep notes in `docs/TEST_LOG.md`).
- Commit to git after every phase.

## Model ownership (HARD RULES)
- NEVER download or load external pretrained weights (no `from_pretrained("gpt2")`, Qwen, Llama, etc.).
- Always build the original model with `GPT2LMHeadModel(config)` (random init).
- Loading OUR OWN checkpoints (written by our training scripts into `checkpoints/`) for
  resuming, task training and inference IS allowed. These are not external pretrained weights.
  Keep the two ideas clearly separate in code and comments.

## Tokenizer
- Byte-level BPE, vocab size 16000, `initial_alphabet=ByteLevel.alphabet()` in `BpeTrainer`.
- Exactly these special tokens: `[PAD] [UNK] [BOS] [EOS] [SCHEMA] [USER] [QUERY]`.
- Model vocab size comes from `tokenizer.get_vocab_size()` after training.
- Verify representative text gives no `[UNK]`.

## Retrain-tokenizer reminder (IMPORTANT)
After Phase 4, retrain the tokenizer on the synthetic data plus starter corpus, then rebuild the
model before any training. Choose the vocab size based on corpus size (target about 8000).
Rebuild in one command: `python model/initialize_model.py tokenizer` (then `python model/verify.py`).

## Data
- General pretraining corpus is kept SEPARATE from synthetic database-search examples.
- Synthetic examples are for task training. Prevent train/validation/test leakage.
- TEST schemas must be completely unseen in training.
- Validate every generated JSON query plan against its expected structure.
- Example format: `[BOS][SCHEMA] ... [USER] question [QUERY] json plan [EOS]`

## Security (HARD RULES)
- The model output is NEVER executed as raw SQL. It is a JSON plan -> validated against the real
  schema -> converted into a safe, parameterized, READ-ONLY query with a row limit.
- Tenant authorization and database permissions are enforced OUTSIDE the model.
- Read-only connections, parameterized SQL, allowlisted identifiers, query timeouts, row limits.
- MongoDB / NoSQL connectors must also validate operations and operators.
- Unknown tables, unknown columns and unauthorized access are rejected deterministically.

## Phases
1 Setup · 2 Tokenizer · 3 Model · 4 Synthetic data · 5 Pretraining · 6 Task training ·
7 Kaggle support · 8 Evaluation · 9 Constrained inference · 10 Connectors + API · 11 README/final.

## Folder layout
`app/` FastAPI · `tokenizer/` · `model/` · `data/{raw,processed}` · `training/` · `checkpoints/` ·
`evaluation/` · `connectors/` · `inference/` · `kaggle/` · `scripts/` · `tests/` · `docs/`

## Environment
- Windows, Python 3.13 venv in `venv/` (activate: `venv\Scripts\activate`).
- CPU-only PyTorch locally; GPU training happens on Kaggle.
