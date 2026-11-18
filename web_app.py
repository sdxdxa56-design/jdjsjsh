import os
import re
import json
import uuid
import requests
from pathlib import Path
from werkzeug.utils import secure_filename
from flask import Flask, request, jsonify, render_template
from core.scanner import safe_extract_zip, run_static_scan

app = Flask(__name__)

GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "")
REPO = os.environ.get("GITHUB_REPO", "sdxdxa56-design/jdjsjsh")
LOCAL_MODEL_PATH = os.environ.get("ZEROHUNTER_LOCAL_MODEL", "")
UPLOAD_BASE = Path("workspace/uploads")
UPLOAD_BASE.mkdir(parents=True, exist_ok=True)

HEADERS = {
    "Authorization": f"token {GITHUB_TOKEN}",
    "Accept": "application/vnd.github.v3+json",
}

_LOCAL_LLM = None


def get_local_llm():
    global _LOCAL_LLM
    if _LOCAL_LLM is not None:
        return _LOCAL_LLM
    if LOCAL_MODEL_PATH and Path(LOCAL_MODEL_PATH).exists():
        from llama_cpp import Llama
        _LOCAL_LLM = Llama(model_path=LOCAL_MODEL_PATH, n_ctx=4096, n_threads=4, verbose=False)
    return _LOCAL_LLM


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/upload", methods=["POST"])
def upload_files():
    session_id = request.form.get("session_id") or uuid.uuid4().hex[:10]
    session_dir = UPLOAD_BASE / re.sub(r"[^A-Za-z0-9_-]", "", session_id)
    session_dir.mkdir(parents=True, exist_ok=True)

    uploaded = request.files.getlist("files")
    if not uploaded:
        return jsonify({"error": "لم يتم اختيار أي ملفات"}), 400

    saved_files = []
    has_zip = False
    for f in uploaded:
        rel_parts = [secure_filename(p) for p in Path(f.filename or "file.txt").parts if p not in ("", ".", "..")]
        if not rel_parts:
            continue
        target = session_dir.joinpath(*rel_parts)
        target.parent.mkdir(parents=True, exist_ok=True)
        f.save(str(target))
        rel_str = "/".join(rel_parts)
        saved_files.append(rel_str)
        if rel_str.lower().endswith(".zip"):
            has_zip = True

    return jsonify({
        "ok": True,
        "session_id": session_dir.name,
        "files": saved_files,
        "has_zip": has_zip,
        "message": f"تم رفع {len(saved_files)} ملف بنجاح. اكتب 'فككه' لفك الأرشيف أو ابدأ المحادثة والفحص.",
    })


def perform_unpack(session_id: str) -> tuple[dict, int]:
    safe_sid = re.sub(r"[^A-Za-z0-9_-]", "", session_id)
    session_dir = UPLOAD_BASE / safe_sid
    if not session_dir.exists():
        return {"ok": False, "error": "الجلسة غير موجودة"}, 404

    extracted = []
    extract_dir = session_dir / "extracted"
    for zp in session_dir.rglob("*.zip"):
        extracted.extend(safe_extract_zip(zp, extract_dir))

    findings = run_static_scan(extract_dir if extract_dir.exists() else session_dir)
    return {
        "ok": True,
        "extracted_count": len(extracted),
        "extracted": extracted[:100],
        "findings": findings[:15],
        "workspace_path": str(extract_dir if extract_dir.exists() else session_dir),
    }, 200


@app.route("/api/unpack/<session_id>", methods=["POST"])
def unpack_session(session_id: str):
    data, code = perform_unpack(session_id)
    return jsonify(data), code


@app.route("/api/chat", methods=["POST"])
def chat():
    payload = request.json or {}
    user_msg = payload.get("message", "").strip()
    session_id = payload.get("session_id", "")
    if not user_msg:
        return jsonify({"error": "الرسالة فارغة"}), 400

    # Handle local "فككه" command directly if an archive was uploaded (avoid matching substrings like "كيفك")
    if session_id and re.search(r"(?:^|[\s،,.:;!?؟«»'()-])(?:فككه|فكك|فك\s+الأرشيف|فك\s+الملف|استخرجه|استخرج|unzip|extract)(?:$|[\s،,.:;!?؟«»'()-])", user_msg.lower()):
        resp_data, code = perform_unpack(session_id)
        if code != 200 or not resp_data.get("ok"):
            return jsonify({"error": resp_data.get("error", "تعذر فك الأرشيف")}), code
        files_preview = "\n".join(f"- {p}" for p in resp_data.get("extracted", [])[:25])
        findings_list = resp_data.get("findings", [])
        findings_preview = "\n".join(f"- {f['file']}:{f['line']}: {f['message']}" for f in findings_list[:6])
        extra = f"\n\n🔎 المسح الأولي رصد {len(findings_list)} نقطة:\n{findings_preview}" if findings_list else ""
        return jsonify({
            "direct_reply": (
                f"📦 تم تفكيك الأرشيف ({resp_data['extracted_count']} ملفاً) في المسار {resp_data['workspace_path']}:\n"
                f"{files_preview}{extra}\n\n💬 كيف تحب أن نبدأ التفاهم حول هذه الملفات؟"
            )
        })

    # If a local GGUF model is loaded, answer directly offline without needing GitHub
    llm = get_local_llm()
    if llm is not None:
        ws_note = ""
        if session_id:
            sdir = UPLOAD_BASE / re.sub(r"[^A-Za-z0-9_-]", "", session_id)
            if sdir.exists():
                all_files = [p for p in sdir.rglob("*") if p.is_file() and p.suffix.lower() != ".zip"]
                rel_names = [str(p.relative_to(sdir)) for p in all_files][:40]
                ws_note = "\nالملفات الموجودة في مساحة العمل:\n" + "\n".join(rel_names)
                if any(k in user_msg.lower() for k in ("افحص", "فحص", "ثغرات", "اشرح", "audit", "scan")):
                    local_findings = run_static_scan(sdir)[:8]
                    if local_findings:
                        ws_note += "\n\nنتائج الفحص الثابت:\n" + json.dumps(local_findings, ensure_ascii=False)
                for p in all_files[:3]:
                    if p.name.lower() in user_msg.lower() or len(all_files) <= 2:
                        try:
                            ws_note += f"\n\nمقتطف من {p.name}:\n" + p.read_text(encoding="utf-8", errors="ignore")[:1800]
                        except OSError:
                            pass
        prompt = (
            "<|im_start|>system\nأنت ZeroHunter، مساعد أمني ذكي تتحدث العربية بطبيعية وتفحص الكود والملفات المرفوعة وتقترح خططاً وأفكاراً.<|im_end|>\n"
            f"<|im_start|>user\n{user_msg}{ws_note}<|im_end|>\n<|im_start|>assistant\n"
        )
        out = llm(prompt, max_tokens=512, stop=["<|im_end|>"], echo=False, temperature=0.2)
        return jsonify({"direct_reply": out["choices"][0]["text"].strip()})

    if not GITHUB_TOKEN:
        return jsonify({"error": "اضبط ZEROHUNTER_LOCAL_MODEL للعمل المحلي أو GITHUB_TOKEN للتشغيل عبر GitHub"}), 500

    url = f"https://api.github.com/repos/{REPO}/issues"
    resp = requests.post(url, headers=HEADERS, json={"title": f"Audit: {user_msg[:40]}", "body": user_msg}, timeout=15)
    if resp.status_code != 201:
        return jsonify({"error": f"فشل إنشاء المهمة في GitHub ({resp.status_code})"}), 500
    return jsonify({"issue_id": resp.json()["number"]})


@app.route("/api/reply/<int:issue_id>", methods=["POST"])
def reply_live(issue_id: int):
    user_msg = (request.json or {}).get("message", "").strip()
    if not user_msg:
        return jsonify({"error": "الرسالة فارغة"}), 400
    url = f"https://api.github.com/repos/{REPO}/issues/{issue_id}/comments"
    resp = requests.post(url, headers=HEADERS, json={"body": f"[USER_CMD] {user_msg}"}, timeout=15)
    if resp.status_code != 201:
        return jsonify({"error": f"فشل إرسال التعليق ({resp.status_code})"}), 500
    return jsonify({"ok": True})


@app.route("/api/status/<int:issue_id>")
def status(issue_id: int):
    url = f"https://api.github.com/repos/{REPO}/issues/{issue_id}/comments?per_page=100"
    resp = requests.get(url, headers=HEADERS, timeout=15)
    if resp.status_code != 200:
        return jsonify({"status": "error", "reply": f"❌ خطأ من GitHub API ({resp.status_code})"}), 500

    raw_comments = resp.json()
    visible = []
    progress_info = {"phase": "جاري التحضير", "progress": 5, "eta_seconds": 180}
    done = False

    for c in raw_comments:
        body = c.get("body", "")
        m = re.search(r"<!-- ZEROHUNTER_STATUS:(.*?) -->", body)
        if m:
            try:
                progress_info = json.loads(m.group(1))
            except json.JSONDecodeError:
                pass
        clean = re.sub(r"<!-- ZEROHUNTER_STATUS:.*? -->", "", body).strip()
        if clean:
            visible.append(clean)
        if "🏁 **التقرير النهائي**" in body or body.startswith("❌"):
            done = True

    return jsonify({
        "status": "done" if done else "working",
        "progress": progress_info,
        "reply": "\n\n---\n\n".join(visible) if visible else "⏳ جاري تشغيل حاوية الوكيل على GitHub Actions...",
    })


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
