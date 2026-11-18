import os
from pathlib import Path
from huggingface_hub import HfApi

HF_TOKEN = os.environ.get("HF_TOKEN")
if not HF_TOKEN:
    raise SystemExit("ERROR: Set HF_TOKEN environment variable before running upload_hf.py")

GGUF_DIR = Path(os.environ.get("ZEROHUNTER_OUT_DIR", "./zerohunter_gguf"))
TARGET_REPO = os.environ.get("ZEROHUNTER_HF_REPO", "sdxdxa56/zerohunter-qwen-gguf")

api = HfApi(token=HF_TOKEN)
api.create_repo(repo_id=TARGET_REPO, exist_ok=True)

gguf_files = list(GGUF_DIR.glob("*.gguf"))
if not gguf_files:
    raise SystemExit(f"No .gguf file found inside {GGUF_DIR}")

for fpath in gguf_files:
    print(f"Uploading {fpath.name} -> {TARGET_REPO}/zerohunter-3b-q4_k_m.gguf...")
    api.upload_file(
        path_or_fileobj=str(fpath),
        path_in_repo="zerohunter-3b-q4_k_m.gguf",
        repo_id=TARGET_REPO,
        repo_type="model",
    )

print(f"Uploaded successfully: https://huggingface.co/{TARGET_REPO}")
