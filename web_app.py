import os
import re
import json
import requests
from flask import Flask, request, jsonify, render_template

app = Flask(__name__)

GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "")
REPO = os.environ.get("GITHUB_REPO", "sdxdxa56-design/jdjsjsh")
HEADERS = {
    "Authorization": f"token {GITHUB_TOKEN}",
    "Accept": "application/vnd.github.v3+json",
}


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/chat", methods=["POST"])
def chat():
    if not GITHUB_TOKEN:
        return jsonify({"error": "GITHUB_TOKEN غير مضبوط في متغيرات البيئة"}), 500
    user_msg = (request.json or {}).get("message", "").strip()
    if not user_msg:
        return jsonify({"error": "الرسالة فارغة"}), 400

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
