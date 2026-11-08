import os, requests, subprocess, json, re

GITHUB_TOKEN = os.environ["GITHUB_TOKEN"]
ISSUE_NUM = os.environ["ISSUE_NUMBER"]
ISSUE_BODY = os.environ.get("ISSUE_BODY", "No instructions")
REPO = os.environ["REPO"]

def post_comment(msg):
    url = f"https://api.github.com/repos/{REPO}/issues/{ISSUE_NUM}/comments"
    headers = {"Authorization": f"token {GITHUB_TOKEN}", "Accept": "application/vnd.github.v3+json"}
    requests.post(url, headers=headers, json={"body": msg})

post_comment(f"🤖 **ZeroHunter:** استلمت الهدف `{ISSUE_BODY}`. جاري التفكير...")

# توجيهات صارمة جداً للنموذج لمنع الأخطاء السابقة
system_prompt = """You are ZeroHunter, a strict cybersecurity AI.
Rules:
1. If the target is a website (starts with http), NEVER use 'git clone'. Use 'nuclei', 'ffuf', or 'nmap'. For nmap, remove 'http://' and 'https://'.
2. If the target is a GitHub repository, use 'git clone' then 'semgrep' or 'clang'.
3. Reply with exactly ONE JSON object: {"action": "run_command", "command": "bash_command"}
OR if done: {"action": "finish", "report": "Report details"}
Do NOT output markdown. ONLY valid JSON."""

messages = [{"role": "system", "content": system_prompt}]
context = f"Target: {ISSUE_BODY}\nHistory:\n"

max_steps = 3 # 3 خطوات كحد أقصى لتسريع الرد
for step in range(max_steps):
    messages.append({"role": "user", "content": context + "\nWhat is your next step?"})
    
    try:
        payload = {"model": "qwen2.5-coder:1.5b", "messages": messages, "stream": False, "format": "json"}
        resp = requests.post("http://127.0.0.1:11434/api/chat", json=payload, timeout=600).json()
        ai_resp = json.loads(resp['message']['content'])
    except Exception as e:
        post_comment(f"❌ فشل الاتصال بالنموذج. (قد يكون النموذج يستهلك ذاكرة كبيرة). الخطأ: {e}")
        break

    if ai_resp.get("action") == "finish":
        post_comment(f"🏁 **التقرير النهائي:**\n\n{ai_resp.get('report')}")
        break
        
    cmd = ai_resp.get("command", "")
    
    # تصحيح تلقائي لأخطاء النموذج الشائعة
    if "nmap" in cmd:
        cmd = cmd.replace("https://", "").replace("http://", "").replace("nmap -sV", "nmap -sV -Pn")
        
    post_comment(f"⚙️ **الخطوة {step+1}:**\n```bash\n{cmd}\n```\n⏳ *جاري التنفيذ...*")
    
    try:
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=300)
        out = result.stdout + result.stderr
        if len(out) > 2000: out = out[:2000] + "\n...[مختصر]"
    except subprocess.TimeoutExpired:
        out = "[انتهى الوقت - الأمر استغرق أكثر من 5 دقائق]"
    except Exception as e:
        out = str(e)
        
    post_comment(f"📊 **النتيجة:**\n```\n{out}\n```")
    context += f"\nStep {step+1}:\nCommand: {cmd}\nOutput: {out}\n"
    messages.append({"role": "assistant", "content": json.dumps(ai_resp)})
