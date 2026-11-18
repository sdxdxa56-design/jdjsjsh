import os
import json
import requests
from pathlib import Path
from typing import List, Dict, Any


def lookup_online_knowledge(query: str, max_items: int = 5) -> str:
    """Queries public defensive vulnerability databases (GitHub Advisories & NVD CVE API)."""
    results: List[str] = []
    headers = {"Accept": "application/vnd.github+json", "User-Agent": "ZeroHunter-Knowledge"}
    gh_token = os.environ.get("GITHUB_TOKEN")
    if gh_token:
        headers["Authorization"] = f"Bearer {gh_token}"

    # 1. GitHub Security Advisories (public open-source vulnerability database)
    try:
        resp = requests.get(
            "https://api.github.com/advisories",
            params={"per_page": max_items, "type": "reviewed"},
            headers=headers,
            timeout=12,
        )
        if resp.status_code == 200:
            q_low = (query or "").lower()
            for adv in resp.json():
                summary = adv.get("summary", "")
                cve = adv.get("cve_id") or adv.get("ghsa_id", "")
                sev = adv.get("severity", "unknown")
                if not q_low or any(w in summary.lower() for w in q_low.split() if len(w) > 3):
                    results.append(f"- [{cve} | {sev}] {summary}")
            if not results:
                for adv in resp.json()[:3]:
                    results.append(f"- [{adv.get('cve_id') or adv.get('ghsa_id')} | {adv.get('severity')}] {adv.get('summary')}")
    except Exception:
        pass

    # 2. NVD CVE 2.0 keyword search when query looks specific
    keywords = [w for w in (query or "").split() if len(w) > 3][:3]
    if keywords:
        try:
            nvd_resp = requests.get(
                "https://services.nvd.nist.gov/rest/json/cves/2.0",
                params={"keywordSearch": " ".join(keywords), "resultsPerPage": 3},
                timeout=12,
            )
            if nvd_resp.status_code == 200:
                for item in nvd_resp.json().get("vulnerabilities", []):
                    cve_obj = item.get("cve", {})
                    cve_id = cve_obj.get("id", "")
                    descs = cve_obj.get("descriptions", [])
                    text = descs[0].get("value", "")[:220] if descs else ""
                    if cve_id and text:
                        results.append(f"- [{cve_id} | NVD] {text}")
        except Exception:
            pass

    return "\n".join(results[:max_items]) if results else "لم تتوفر مراجع مطابقة من الإنترنت حالياً."


def build_curated_dataset(out_path: str = "datasets/auto_curated.jsonl", limit: int = 40) -> int:
    """Fetches reviewed security advisories from public feeds and saves ChatML training records."""
    headers = {"Accept": "application/vnd.github+json", "User-Agent": "ZeroHunter-AutoLearn"}
    gh_token = os.environ.get("GITHUB_TOKEN")
    if gh_token:
        headers["Authorization"] = f"Bearer {gh_token}"

    records: List[Dict[str, Any]] = []
    try:
        resp = requests.get(
            "https://api.github.com/advisories",
            params={"per_page": limit, "type": "reviewed"},
            headers=headers,
            timeout=20,
        )
        if resp.status_code == 200:
            for adv in resp.json():
                summary = (adv.get("summary") or "").strip()
                desc = (adv.get("description") or "").strip()[:900]
                cve = adv.get("cve_id") or adv.get("ghsa_id", "Advisory")
                sev = adv.get("severity", "medium")
                if not summary or not desc:
                    continue
                records.append({
                    "conversations": [
                        {
                            "role": "system",
                            "content": "أنت ZeroHunter، مساعد أمني خبير تشرح الثغرات وتقترح خطط الإصلاح بالعربية بوضوح.",
                        },
                        {
                            "role": "user",
                            "content": f"اشرح الثغرة {cve} ({sev}): {summary}\nالتفاصيل: {desc}",
                        },
                        {
                            "role": "assistant",
                            "content": (
                                f"📌 **ملخص الثغرة ({cve} - الخطورة: {sev}):** {summary}\n"
                                f"💡 **خطة المعالجة والتحقق:** راجع المكون المتأثر في الشيفرة المصدرية، حدّث التبعية للنسخة الآمنة الموصى بها، وأضف اختبار وحدة أو Fuzzer لمنع تكرار الخلل."
                            ),
                        },
                    ]
                })
    except Exception as exc:
        print("Advisory fetch warning:", exc)

    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8") as fh:
        for rec in records:
            fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
    print(f"Saved {len(records)} curated records to {out}")
    return len(records)
