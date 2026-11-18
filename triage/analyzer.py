from pathlib import Path
from typing import Dict, Any, List


def summarize_crash_for_llm(asan_log: str, source_excerpt: str) -> str:
    """Extracts key ASan lines to keep triage prompt compact and focused."""
    important_lines: List[str] = []
    for line in asan_log.splitlines():
        if any(tok in line for tok in ("ERROR:", "SUMMARY:", "WRITE of size", "READ of size", "#0 ", "#1 ", "#2 ", "Test unit written to")):
            important_lines.append(line)
    trace = "\n".join(important_lines[:20]) or asan_log[-1000:]
    return (
        f"ASan / UBSan Trace:\n{trace}\n\n"
        f"Relevant Source Code:\n{source_excerpt}"
    )


def save_markdown_report(title: str, sections: List[str], out_path: str = "reports/final_report.md") -> Path:
    path = Path(out_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    body = f"# {title}\n\n" + "\n\n---\n\n".join(sections)
    path.write_text(body, encoding="utf-8")
    return path
