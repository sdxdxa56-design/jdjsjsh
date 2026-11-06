import os, requests, subprocess
GITHUB_TOKEN = os.environ["GITHUB_TOKEN"]
ISSUE_NUM = os.environ["ISSUE_NUMBER"]
ISSUE_BODY = os.environ.get("ISSUE_BODY", "No instructions")
REPO = os.environ["REPO"]
def post_comment(msg):
    url = f"https://api.github.com/repos/{REPO}/issues/{ISSUE_NUM}/comments"
    headers = {"Authorization": f"token {GITHUB_TOKEN}", "Accept": "application/vnd.github.v3+json"}
    requests.post(url, headers=headers, json={"body": msg})
post_comment("🤖 **ZeroHunter:** جاري التفكير وكتابة الأمر...")
prompt = f'You are a security agent. User asked: "{ISSUE_BODY}". Write EXACTLY ONE bash command. No markdown.'
try:
    resp = requests.post("http://127.0.0.1:11434/api/generate", json={"model": "qwen2.5-coder:1.5b", "prompt": prompt, "stream": False}, timeout=120).json()
    cmd = resp['response'].strip().replace("```bash", "").replace("```", "").strip()
    post_comment(f"⚙️ **الأمر:**\n```bash\n{cmd}\n```\n⏳ *جاري التنفيذ...*")
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=300)
    out = result.stdout + result.stderr
    if len(out) > 3500: out = out[:3500] + "\n...[مختصر]"
    post_comment(f"✅ **النتيجة:**\n```\n{out}\n```\n🧠 *أضف تعليقاً للمتابعة.*")
except Exception as e:
    post_comment(f"❌ خطأ: {e}")
