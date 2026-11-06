import os, requests, time
from flask import Flask, request, jsonify, render_template

app = Flask(__name__)

GITHUB_TOKEN = os.environ.get("GIT_TOKEN", "ضع_التوكن_هنا")
REPO = "sdxdxa56-design/jdjsjsh"
HEADERS = {"Authorization": f"token {GITHUB_TOKEN}", "Accept": "application/vnd.github.v3+json"}

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/api/chat", methods=["POST"])
def chat():
    user_msg = request.json.get("message")
    # إنشاء Issue جديد في GitHub
    url = f"https://api.github.com/repos/{REPO}/issues"
    payload = {"title": f"Chat: {user_msg[:30]}...", "body": user_msg}
    resp = requests.post(url, headers=HEADERS, json=payload)
    if resp.status_code != 201:
        return jsonify({"error": "فشل إنشاء Issue في GitHub"}), 500
    
    issue_number = resp.json()["number"]
    return jsonify({"issue_id": issue_number})

@app.route("/api/status/<int:issue_id>")
def status(issue_id):
    # جلب التعليقات من الـ Issue
    url = f"https://api.github.com/repos/{REPO}/issues/{issue_id}/comments"
    resp = requests.get(url, headers=HEADERS).json()
    comments = [c["body"] for c in resp]
    
    # إذا وجدنا رد البوت (يبدأ بـ ✅ أو ❌)
    for c in comments:
        if "✅ **النتيجة:**" in c or "❌ خطأ:" in c:
            return jsonify({"status": "done", "reply": c})
    
    # إذا لم ينته بعد، نرجع أقصى تعليق موجود حالياً
    last_comment = comments[-1] if comments else "⏳ جاري تشغيل السيرفر والذكاء الاصطناعي (قد يأخذ دقيقتين)..."
    return jsonify({"status": "working", "reply": last_comment})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
