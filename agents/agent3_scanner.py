import argparse
import gzip
import json
import re
import zipfile
from pathlib import Path
from typing import Dict, List

WEIGHTS_PATH = Path("models/agent3_scanner_weights.json.gz")

RISK_TRAINING_RULES = [
    ("android:debuggable", "critical", "ZH-APK-DEBUGGABLE", 0.98),
    ("TrustAllCerts", "critical", "ZH-APK-SSL-BYPASS", 0.96),
    ("AIza", "critical", "ZH-SECRET-EXPOSED", 0.95),
    ("strcpy", "critical", "ZH-C-STRCPY", 0.94),
    ("pickle.loads", "critical", "ZH-PY-DESERIAL", 0.93),
    ("addJavascriptInterface", "high", "ZH-APK-WEBVIEW", 0.89),
    ("usesCleartextTraffic", "high", "ZH-APK-CLEARTEXT", 0.86),
    ("exported", "high", "ZH-APK-EXPORTED", 0.82),
    ("rawQuery", "high", "ZH-SQL-INJECTION", 0.84),
    ("allowBackup", "medium", "ZH-APK-BACKUP", 0.70),
]


class DeepScannerAgent:
    def __init__(self, weights_path: Path = WEIGHTS_PATH):
        self.weights_path = weights_path
        self.rules: List[Dict[str, object]] = []
        if self.weights_path.exists():
            self.load()

    def train_from_scratch(self) -> Dict[str, object]:
        self.rules = [
            {"pattern": pat, "severity": sev, "rule_id": rid, "weight": w}
            for pat, sev, rid, w in RISK_TRAINING_RULES
        ]
        self.weights_path.parent.mkdir(parents=True, exist_ok=True)
        with gzip.open(self.weights_path, "wt", encoding="utf-8") as gz:
            json.dump({"rules": self.rules, "version": 1}, gz, ensure_ascii=False)
        return {
            "agent": "agent3_scanner",
            "rules_trained": len(self.rules),
            "size_kb": round(self.weights_path.stat().st_size / 1024, 2),
        }

    def load(self) -> None:
        with gzip.open(self.weights_path, "rt", encoding="utf-8") as gz:
            data = json.load(gz)
        self.rules = data.get("rules", [])

    def inspect_apk(self, apk_path: Path) -> Dict[str, object]:
        findings: List[Dict[str, object]] = []
        endpoints: List[str] = []
        if not apk_path.exists():
            return {"ok": False, "findings": findings, "endpoints": endpoints}
        try:
            with zipfile.ZipFile(apk_path, "r") as zf:
                names = zf.namelist()
                for name in names:
                    low = name.lower()
                    if low.endswith(".dex") or low.endswith(".xml") or low.endswith(".json"):
                        raw = zf.read(name)[:400_000]
                        ascii_strings = re.findall(rb"[A-Za-z0-9_./:?=&-]{6,180}", raw)
                        decoded = "\n".join(s.decode("ascii", errors="ignore") for s in ascii_strings)
                        for rule in self.rules:
                            pat = str(rule["pattern"])
                            if pat in decoded:
                                findings.append({
                                    "file": name,
                                    "rule_id": rule["rule_id"],
                                    "severity": rule["severity"],
                                    "confidence": rule["weight"],
                                })
                        for url_m in re.findall(r"https?://[A-Za-z0-9.-]+\.[A-Za-z]{2,}[^\s<>\x22']*", decoded):
                            if "schemas.android.com" not in url_m and len(endpoints) < 30:
                                endpoints.append(url_m)
        except Exception as exc:
            return {"ok": False, "error": str(exc), "findings": findings, "endpoints": endpoints}
        return {"ok": True, "findings": findings[:25], "endpoints": list(dict.fromkeys(endpoints))}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--train", action="store_true")
    args = parser.parse_args()
    agent = DeepScannerAgent()
    if args.train:
        print(json.dumps(agent.train_from_scratch(), ensure_ascii=False))
