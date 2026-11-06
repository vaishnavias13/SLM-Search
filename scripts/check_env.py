"""Phase 1 check: are all libraries installed, and does PyTorch see a GPU?"""
import importlib
import sys

PACKAGES = [
    "torch", "transformers", "tokenizers", "datasets", "accelerate", "pandas", "numpy",
    "safetensors", "fastapi", "uvicorn", "pydantic", "sqlalchemy", "sqlglot", "pymongo",
    "pytest", "httpx",
]

print("Python:", sys.version.split()[0])
failed = []
for name in PACKAGES:
    try:
        mod = importlib.import_module(name)
        print(f"  OK   {name:14s} {getattr(mod, '__version__', '?')}")
    except Exception as exc:  # noqa: BLE001
        failed.append(name)
        print(f"  FAIL {name:14s} {exc}")

import torch  # noqa: E402

print("CUDA available:", torch.cuda.is_available())
if torch.cuda.is_available():
    print("GPU:", torch.cuda.get_device_name(0))
else:
    print("No GPU here (normal). Real training will use Kaggle's GPU.")

if failed:
    print("MISSING:", failed)
    sys.exit(1)
print("Environment check PASSED")
