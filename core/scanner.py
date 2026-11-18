import os
import re
import json
import subprocess
from pathlib import Path
from typing import List, Dict, Any


RISKY_C_SINKS = re.compile(r"\b(strcpy|strcat|memcpy|memmove|sprintf|vsprintf|gets|scanf)\s*\(")
RISKY_PY_SINKS = re.compile(r"(subprocess\.|os\.system|pickle\.loads|yaml\.load|eval\(|exec\()")


def safe_extract_zip(zip_path: Path, dest_dir: Path) -> List[str]:
    """Safely extracts a .zip archive preventing Zip-Slip path traversal."""
    import zipfile
    extracted: List[str] = []
    dest_root = dest_dir.resolve()
    dest_root.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_path, "r") as zf:
        for member in zf.infolist():
            if member.is_dir():
                continue
            target_path = (dest_root / member.filename).resolve()
            if not str(target_path).startswith(str(dest_root)):
                continue
            target_path.parent.mkdir(parents=True, exist_ok=True)
            with zf.open(member) as src, target_path.open("wb") as dst:
                dst.write(src.read())
            extracted.append(member.filename)
    return extracted


def clone_or_prepare_workspace(target_spec: str, workdir: Path) -> Path:
    """Prepares a local uploaded folder, unpacked archive, or cloned authorized repository."""
    workdir.mkdir(parents=True, exist_ok=True)
    local_match = re.search(r"workspace/uploads/[A-Za-z0-9_.-]+", target_spec or "")
    if local_match and Path(local_match.group(0)).exists():
        return Path(local_match.group(0))
    url_match = re.search(r"https://github\.com/[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", target_spec or "")
    if url_match:
        repo_url = url_match.group(0)
        dest = workdir / "target_repo"
        if not dest.exists():
            subprocess.run(
                ["git", "clone", "--depth", "1", repo_url, str(dest)],
                check=False,
                capture_output=True,
                text=True,
                timeout=120,
            )
        if dest.exists():
            return dest
    return Path("targets")


def run_static_scan(target_dir: Path) -> List[Dict[str, Any]]:
    """Runs deterministic static analyzers and pattern heuristics across C/C++, Python, and configs."""
    findings: List[Dict[str, Any]] = []

    if not target_dir.exists():
        return findings

    # 1. Run cppcheck for C/C++ if files exist
    c_files = list(target_dir.rglob("*.c")) + list(target_dir.rglob("*.cpp"))
    if c_files:
        res = subprocess.run(
            ["cppcheck", "--enable=warning,performance,portability", "--template={file}:{line}:{severity}:{message}", str(target_dir)],
            capture_output=True,
            text=True,
            timeout=120,
        )
        for line in (res.stderr or "").splitlines():
            parts = line.split(":", 3)
            if len(parts) == 4:
                findings.append({
                    "tool": "cppcheck",
                    "file": parts[0],
                    "line": int(parts[1]) if parts[1].isdigit() else 1,
                    "severity": parts[2],
                    "message": parts[3].strip(),
                })

    # 2. Run semgrep if available
    semgrep_res = subprocess.run(
        ["semgrep", "--config", "auto", "--json", "--quiet", str(target_dir)],
        capture_output=True,
        text=True,
        timeout=180,
    )
    if semgrep_res.returncode in (0, 1) and semgrep_res.stdout.strip():
        try:
            data = json.loads(semgrep_res.stdout)
            for item in data.get("results", [])[:25]:
                findings.append({
                    "tool": "semgrep",
                    "file": item.get("path", ""),
                    "line": item.get("start", {}).get("line", 1),
                    "severity": item.get("extra", {}).get("severity", "WARNING"),
                    "message": item.get("extra", {}).get("message", item.get("check_id", "")),
                })
        except json.JSONDecodeError:
            pass

    # 3. Fast fallback sink scan so small targets like demo.c are always captured
    for path in target_dir.rglob("*"):
        if not path.is_file() or path.suffix not in {".c", ".cpp", ".h", ".py", ".js", ".ts", ".conf"}:
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        for idx, line in enumerate(text.splitlines(), start=1):
            if path.suffix in {".c", ".cpp", ".h"} and RISKY_C_SINKS.search(line):
                findings.append({
                    "tool": "sink-heuristic",
                    "file": str(path),
                    "line": idx,
                    "severity": "high",
                    "message": f"Risky C memory operation: {line.strip()[:120]}",
                })
            elif path.suffix == ".py" and RISKY_PY_SINKS.search(line):
                findings.append({
                    "tool": "sink-heuristic",
                    "file": str(path),
                    "line": idx,
                    "severity": "high",
                    "message": f"Risky Python call: {line.strip()[:120]}",
                })

    # Deduplicate by (file, line, tool)
    seen = set()
    unique: List[Dict[str, Any]] = []
    for f in findings:
        key = (f["file"], f["line"], f["tool"])
        if key not in seen:
            seen.add(key)
            unique.append(f)
    return unique[:30]


def extract_target_context(file_path: str, center_line: int, radius: int = 25) -> str:
    """Extracts a bounded code window around a suspicious line so it fits inside LLM context."""
    p = Path(file_path)
    if not p.exists():
        return ""
    lines = p.read_text(encoding="utf-8", errors="ignore").splitlines()
    start = max(0, center_line - radius - 1)
    end = min(len(lines), center_line + radius)
    return "\n".join(f"{i + 1}: {lines[i]}" for i in range(start, end))
