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

candidates = []
for search_root in (GGUF_DIR, Path(f"{GGUF_DIR}_gguf"), Path(".")):
    if search_root.exists():
        candidates.extend(search_root.rglob("*.gguf"))

# Deduplicate while preferring inside GGUF_DIR
seen = set()
gguf_files = []
for p in candidates:
    rp = p.resolve()
    if rp not in seen and "checkpoint" not in str(rp):
        seen.add(rp)
        gguf_files.append(p)

if not gguf_files:
    raise SystemExit(f"No .gguf file found inside {GGUF_DIR} or current directory")

chosen = sorted(gguf_files, key=lambda p: p.stat().st_size, reverse=True)[0]
print(f"Uploading {chosen} -> {TARGET_REPO}/zerohunter-3b-q4_k_m.gguf...")
api.upload_file(
    path_or_fileobj=str(chosen),
    path_in_repo="zerohunter-3b-q4_k_m.gguf",
    repo_id=TARGET_REPO,
    repo_type="model",
)

print(f"Uploaded successfully: https://huggingface.co/{TARGET_REPO}")
