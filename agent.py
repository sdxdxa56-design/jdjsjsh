import os, requests, subprocess, json

GITHUB_TOKEN = os.environ["GITHUB_TOKEN"]
ISSUE_NUM = os.environ["ISSUE_NUMBER"]
ISSUE_BODY = os.environ.get("ISSUE_BODY", "No instructions")
REPO = os.environ["REPO"]
HF_TOKEN = os.environ["HF_TOKEN"] # سنضيف هذا في الخطوة التالية

def post_comment(msg):
    url = f"https://api.github.com/repos/{REPO}/issues/{ISSUE_NUM}/comments"
    headers = {"Authorization": f"token {GITHUB_TOKEN}", "Accept": "application/vnd.github.v3+json"}
    requests.post(url, headers=headers, json={"body": msg})

post_comment(f"🤖 **ZeroHunter (النموذج المخصص):** استلمت الهدف `{ISSUE_BODY}`. جاري التحليل...")

# رابط النموذج الخاص بك على Hugging Face
API_URL = "https://api-inference.huggingface.co/models/sdxdxa56/zerohunter-qwen-7b"
headers = {"Authorization": f"Bearer {HF_TOKEN}"}

prompt = f"""You are ZeroHunter, an elite cybersecurity AI.
Analyze this target and provide a bash command to test it, or a report if a vulnerability is found.
Target: {ISSUE_BODY}
Reply ONLY with valid JSON: {"action": "run_command", "command": "bash_command"} OR {"action": "finish", "report": "report details"}."""

try:
    payload = {"inputs": prompt, "parameters": {"max_new_tokens": 250, "return_full_text": False}}
    response = requests.post(API_URL, headers=headers, json=payload, timeout=60)
    ai_reply = response.json()[0]['generated_text']
    
    # تنظيف الرد لاستخراج JSON
    ai_reply = ai_reply.replace("```json", "").replace("```", "").strip()
    ai_resp = json.loads(ai_reply)
    
    if ai_resp.get("action") == "finish":
        post_comment(f"🚨 **تقرير النموذج الخاص:**\n\n{ai_resp.get('report')}")
    else:
        cmd = ai_resp.get("command")
        post_comment(f"⚙️ **الأمر:**\n```bash\n{cmd}\n```\n⏳ *جاري التنفيذ...*")
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=300)
        post_comment(f"📊 **النتيجة:**\n```\n{result.stdout[:1000]}\n```")

except Exception as e:
    post_comment(f"❌ خطأ في الاتصال بالنموذج: {e}")
