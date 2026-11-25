import argparse
import gzip
import json
import math
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Dict, List

WEIGHTS_PATH = Path("models/agent2_commander_weights.json.gz")

ROUTING_CORPUS: List[tuple] = [
    ("افحص ملف apk والمانيفست والثغرات", "scan_apk"),
    ("فكك التطبيق واستخرج الصلاحيات والروابط", "scan_apk"),
    ("افحص الكود وابحث عن buffer overflow أو sql injection", "scan_code"),
    ("دقق الشيفرة البرمجية واكتب التصحيح", "scan_code"),
    ("سرّع عمليات github actions والكاش", "accelerate_github"),
    ("حسّن سرعة الرد وتشغيل النموذج في colab", "accelerate_github"),
    ("مرحبا من انت كيف حالك اشرح لي فكرة", "natural_chat"),
    ("تحدث معي وساعدني في تصميم خطة المشروع", "natural_chat"),
]


class CommanderAgent:
    def __init__(self, weights_path: Path = WEIGHTS_PATH):
        self.weights_path = weights_path
        self.class_priors: Dict[str, float] = {}
        self.word_probs: Dict[str, Dict[str, float]] = {}
        self.vocab: List[str] = []
        if self.weights_path.exists():
            self.load()

    def train_from_scratch(self) -> Dict[str, object]:
        class_counts: Counter = Counter()
        word_counts: Dict[str, Counter] = defaultdict(Counter)
        vocab_set = set()
        for text, label in ROUTING_CORPUS:
            class_counts[label] += 1
            for tok in re.findall(r"[\w\u0600-\u06FF]+", text.lower()):
                word_counts[label][tok] += 1
                vocab_set.add(tok)

        total_docs = max(1, len(ROUTING_CORPUS))
        self.vocab = sorted(vocab_set)
        v_size = max(1, len(self.vocab))
        self.class_priors = {c: math.log(cnt / total_docs) for c, cnt in class_counts.items()}
        self.word_probs = {}
        for c in class_counts:
            denom = sum(word_counts[c].values()) + v_size
            self.word_probs[c] = {w: math.log((word_counts[c][w] + 1) / denom) for w in self.vocab}
            self.word_probs[c]["__UNK__"] = math.log(1 / denom)

        self.weights_path.parent.mkdir(parents=True, exist_ok=True)
        with gzip.open(self.weights_path, "wt", encoding="utf-8") as gz:
            json.dump({"priors": self.class_priors, "probs": self.word_probs, "vocab": self.vocab}, gz, ensure_ascii=False)

        return {
            "agent": "agent2_commander",
            "classes": list(self.class_priors.keys()),
            "vocab": len(self.vocab),
            "size_kb": round(self.weights_path.stat().st_size / 1024, 2),
        }

    def load(self) -> None:
        with gzip.open(self.weights_path, "rt", encoding="utf-8") as gz:
            data = json.load(gz)
        self.class_priors = data.get("priors", {})
        self.word_probs = data.get("probs", {})
        self.vocab = data.get("vocab", [])

    def route(self, prompt: str) -> Dict[str, object]:
        if not self.class_priors:
            return {"intent": "hybrid", "pipeline": ["agent1_chat", "agent3_scanner", "qwen_llm"]}
        toks = re.findall(r"[\w\u0600-\u06FF]+", prompt.lower())
        best_cls = "natural_chat"
        best_score = float("-inf")
        for c, prior in self.class_priors.items():
            score = prior
            probs = self.word_probs.get(c, {})
            unk = probs.get("__UNK__", -8.0)
            for t in toks:
                score += probs.get(t, unk)
            if score > best_score:
                best_score = score
                best_cls = c
        pipelines = {
            "scan_apk": ["agent3_scanner", "agent1_chat", "qwen_llm"],
            "scan_code": ["agent3_scanner", "agent1_chat", "qwen_llm"],
            "accelerate_github": ["agent4_accelerator", "agent1_chat", "qwen_llm"],
            "natural_chat": ["agent1_chat", "qwen_llm"],
        }
        return {"intent": best_cls, "pipeline": pipelines.get(best_cls, ["agent1_chat", "qwen_llm"])}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--train", action="store_true")
    args = parser.parse_args()
    agent = CommanderAgent()
    if args.train:
        print(json.dumps(agent.train_from_scratch(), ensure_ascii=False))
