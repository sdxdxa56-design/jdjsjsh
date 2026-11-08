import os, requests, subprocess, json, re

GITHUB_TOKEN = os.environ["GITHUB_TOKEN"]
ISSUE_NUM = os.environ["ISSUE_NUMBER"]
ISSUE_BODY = os.environ.get("ISSUE_BODY", "No instructions")
REPO = os.environ["REPO"]
HF_TOKEN = os.environ.get("HF_TOKEN", "")

def post_comment(msg):
    url = f"https://api.github.com/repos/{REPO}/issues/{ISSUE_NUM}/comments"
    headers = {"Authorization": f"token {GITHUB_TOKEN}", "Accept": "application/vnd.github.v3+json"}
    requests.post(url, headers=headers, json={"body": msg})

post_comment(f"🤖 **ZeroHunter (النموذج المخصص):** استلمت الهدف `{ISSUE_BODY}`. جاري التحليل...")

# ✅ نقطة النهاية الجديدة من Hugging Face
API_URL = "https://router.huggingface.co/v1/chat/completions"
headers = {"Authorization": f"Bearer {HF_TOKEN}", "Content-Type": "application/json"}

prompt = f"""You are ZeroHunter, an elite cybersecurity AI.
Analyze this target and provide a bash command to test it, or a report if a vulnerability is found.
Target: {ISSUE_BODY}
Reply ONLY with valid JSON: {{"action": "run_command", "command": "bash_command"}} OR {{"action": "finish", "report": "report details"}}."""

try:
    # ✅ تنسيق الطلب الجديد (OpenAI-compatible)
    payload = {
        "model": "sdxdxa56/zerohunter-qwen-7b",
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": 250,
        "stream": False
    }
    response = requests.post(API_URL, headers=headers, json=payload, timeout=120)
    
    if response.status_code != 200:
        post_comment(f"❌ فشل الاتصال بالنموذج. الكود: {response.status_code}\nالرد: {response.text}")
        exit(1)
        
    result = response.json()
    ai_reply = result['choices'][0]['message']['content']
    
    # استخراج الـ JSON فقط في حال أضاف النموذج نصوصاً أخرى
    json_match = re.search(r'\{.*\}', ai_reply, re.DOTALL)
    if json_match:
        ai_reply = json_match.group(0)
        
    ai_resp = json.loads(ai_reply)

    if ai_resp.get("action") == "finish":
        post_comment(f"🚨 **تقرير النموذج الخاص:**\n\n{ai_resp.get('report')}")
    else:
        cmd = ai_resp.get("command")
        post_comment(f"⚙️ **الأمر:**\n```bash\n{cmd}\n```\n⏳ *جاري التنفيذ...*")
        result_cmd = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=300)
        out = result_cmd.stdout + result_cmd.stderr
        if len(out) > 1500: out = out[:1500] + "\n...[مختصر]"
        post_comment(f"📊 **النتيجة:**\n```\n{out}\n```")

except json.JSONDecodeError:
    post_comment(f"❌ النموذج أرجع رداً غير صالح (ليس JSON):\n```\n{ai_reply}\n```")
except Exception as e:
    post_comment(f"❌ خطأ غير متوقع: {e}")
