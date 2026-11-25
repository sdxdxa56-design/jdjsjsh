import argparse
import json
from pathlib import Path
from typing import Dict, List

PROFILE_PATH = Path("models/agent4_accelerator_profile.json")


class GitHubAcceleratorAgent:
    def __init__(self, profile_path: Path = PROFILE_PATH):
        self.profile_path = profile_path
        self.profile: Dict[str, object] = {}
        if self.profile_path.exists():
            self.load()

    def train_from_scratch(self) -> Dict[str, object]:
        workflows = sorted(str(p) for p in Path(".github/workflows").glob("*.yml")) if Path(".github/workflows").exists() else []
        model_files = sorted(str(p) for p in Path("models").glob("*")) if Path("models").exists() else []
        oversized: List[str] = []
        for mf in model_files:
            sz = Path(mf).stat().st_size
            if sz > 10 * 1024 * 1024:
                oversized.append(mf)

        gitignore_text = Path(".gitignore").read_text(encoding="utf-8", errors="ignore") if Path(".gitignore").exists() else ""
        models_ignored = any(line.strip() in ("models", "models/", "/models/") for line in gitignore_text.splitlines())

        self.profile = {
            "agent": "agent4_accelerator",
            "flat_cache_dir": ".zh_models",
            "workflows_audited": workflows,
            "compact_weights_ok": len(oversized) == 0,
            "models_gitignored": models_ignored,
            "oversized_files": oversized,
            "recommended_cpu_model": "Qwen/Qwen2.5-Coder-1.5B-Instruct-GGUF",
            "recommended_colab_model": "Qwen/Qwen2.5-Coder-7B-Instruct-GGUF",
        }
        self.profile_path.parent.mkdir(parents=True, exist_ok=True)
        self.profile_path.write_text(json.dumps(self.profile, ensure_ascii=False, indent=2), encoding="utf-8")
        return self.profile

    def load(self) -> None:
        self.profile = json.loads(self.profile_path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--train", action="store_true")
    args = parser.parse_args()
    agent = GitHubAcceleratorAgent()
    if args.train:
        print(json.dumps(agent.train_from_scratch(), ensure_ascii=False))
