import argparse
import gzip
import json
import math
import re
from collections import Counter
from pathlib import Path
from typing import Dict, List, Tuple

WEIGHTS_PATH = Path("models/agent1_chat_weights.json.gz")
DATASET_PATH = Path("datasets/agent1_chat_train.jsonl")

SEED_DIALOGUES: List[Tuple[str, str]] = [
    ("اشرح الكود ووظيفة التطبيق", "أقرأ بنية الملفات المرفوعة أولاً ثم أشرح غرض التطبيق، التقنيات المستخدمة، وأهم المكونات بدون تخمين."),
    ("ما هي الثغرات الخطيرة في اندرويد apk", "أهم ثغرات Android APK تشمل تفعيل debuggable، تصدير مكونات exported بدون صلاحية، WebView addJavascriptInterface، مفاتيح API مكشوفة، وحركة HTTP غير مشفرة."),
    ("تحدث معي بحرية واشرح لي الفكرة", "أهلاً بك! أتحدث معك بشكل طبيعي ومباشر في البرمجة، تحليل التطبيقات، أو تصميم الحلول خطوة بخطوة."),
    ("كيف نصلح ثغرة buffer overflow في c", "نستبدل الدوال غير المقيدة مثل strcpy وmemcpy بمقارنة الطول مع sizeof المخزن الهدف قبل النسخ."),
    ("كيف أسرع استجابة النموذج", "تشغيل GGUF داخل ذاكرة GPU دائمة عبر Colab T4 أو خادم Gemini السريع يختصر الزمن إلى 1-3 ثوانٍ."),
    ("حلل ملف AndroidManifest و strings", "أستخرج الحزمة والأذونات والمكونات المصدرة من AndroidManifest وأبحث عن المفاتيح والروابط المكشوفة في strings وDEX."),
]


def _tokenize(text: str) -> List[str]:
    tokens = re.findall(r"[\w\u0600-\u06FF]+", text.lower())
    bigrams = [f"{tokens[i]}_{tokens[i + 1]}" for i in range(len(tokens) - 1)]
    return tokens + bigrams


class ChatLanguageAgent:
    def __init__(self, weights_path: Path = WEIGHTS_PATH):
        self.weights_path = weights_path
        self.idf: Dict[str, float] = {}
        self.memory: List[Dict[str, object]] = []
        if self.weights_path.exists():
            self.load()

    def train_from_scratch(self) -> Dict[str, object]:
        samples: List[Tuple[str, str]] = list(SEED_DIALOGUES)
        for p in (DATASET_PATH, Path("datasets/auto_curated.jsonl")):
            if p.exists():
                for line in p.read_text(encoding="utf-8", errors="ignore").splitlines():
                    try:
                        obj = json.loads(line)
                        msgs = obj.get("messages") or obj.get("conversations") or []
                        if len(msgs) >= 2:
                            u = str(msgs[-2].get("content") or msgs[-2].get("value") or "").strip()
                            a = str(msgs[-1].get("content") or msgs[-1].get("value") or "").strip()
                            if u and a:
                                samples.append((u, a[:600]))
                    except Exception:
                        continue

        doc_freq: Counter = Counter()
        tokenized_docs: List[Tuple[Counter, str, str]] = []
        for q, ans in samples:
            toks = _tokenize(q)
            tf = Counter(toks)
            for t in tf:
                doc_freq[t] += 1
            tokenized_docs.append((tf, q, ans))

        n_docs = max(1, len(tokenized_docs))
        self.idf = {t: math.log((n_docs + 1) / (df + 1)) + 1.0 for t, df in doc_freq.items()}
        self.memory = []
        for tf, q, ans in tokenized_docs:
            vec = {t: (c / max(1, sum(tf.values()))) * self.idf.get(t, 1.0) for t, c in tf.items()}
            self.memory.append({"q": q, "a": ans, "vec": vec})

        self.weights_path.parent.mkdir(parents=True, exist_ok=True)
        with gzip.open(self.weights_path, "wt", encoding="utf-8") as gz:
            json.dump({"vocab_size": len(self.idf), "idf": self.idf, "memory": self.memory}, gz, ensure_ascii=False)

        DATASET_PATH.parent.mkdir(parents=True, exist_ok=True)
        with DATASET_PATH.open("w", encoding="utf-8") as f:
            for q, ans in samples[:80]:
                f.write(json.dumps({"messages": [{"role": "user", "content": q}, {"role": "assistant", "content": ans}]}, ensure_ascii=False) + "\n")

        return {
            "agent": "agent1_chat",
            "samples": len(self.memory),
            "vocab": len(self.idf),
            "size_kb": round(self.weights_path.stat().st_size / 1024, 2),
        }

    def load(self) -> None:
        with gzip.open(self.weights_path, "rt", encoding="utf-8") as gz:
            data = json.load(gz)
        self.idf = data.get("idf", {})
        self.memory = data.get("memory", [])

    def suggest_context(self, query: str, top_k: int = 2) -> List[str]:
        if not self.memory:
            return []
        q_tf = Counter(_tokenize(query))
        q_vec = {t: (c / max(1, sum(q_tf.values()))) * self.idf.get(t, 1.0) for t, c in q_tf.items()}
        q_norm = math.sqrt(sum(v * v for v in q_vec.values())) or 1.0
        scored = []
        for item in self.memory:
            m_vec = item.get("vec", {})
            dot = sum(q_vec[t] * m_vec.get(t, 0.0) for t in q_vec)
            m_norm = math.sqrt(sum(v * v for v in m_vec.values())) or 1.0
            scored.append((dot / (q_norm * m_norm), str(item.get("a", ""))))
        scored.sort(key=lambda x: x[0], reverse=True)
        return [ans for score, ans in scored[:top_k] if score > 0.05]


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--train", action="store_true")
    args = parser.parse_args()
    agent = ChatLanguageAgent()
    if args.train:
        print(json.dumps(agent.train_from_scratch(), ensure_ascii=False))
