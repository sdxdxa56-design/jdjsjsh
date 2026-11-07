import os, requests, subprocess, json, re

GITHUB_TOKEN = os.environ["GITHUB_TOKEN"]
ISSUE_NUM = os.environ["ISSUE_NUMBER"]
ISSUE_BODY = os.environ.get("ISSUE_BODY", "No instructions")
REPO = os.environ["REPO"]

def post_comment(msg):
    url = f"https://api.github.com/repos/{REPO}/issues/{ISSUE_NUM}/comments"
    headers = {"Authorization": f"token {GITHUB_TOKEN}", "Accept": "application/vnd.github.v3+json"}
    requests.post(url, headers=headers, json={"body": msg})

post_comment(f"🤖 **ZeroHunter (7B):** استلمت طلبك: `{ISSUE_BODY}`\nسأبدأ العمل في حلقات (تحليل -> تنفيذ -> تقييم). يرجى الانتظار...")

system_prompt = """You are ZeroHunter, an autonomous penetration testing AI.
You have access to: nmap, nuclei, ffuf, gobuster, subfinder, clang, and Linux tools.
You operate in a loop. I give you the objective and history. 
Reply with exactly ONE JSON object:
{"action": "run_command", "command": "bash_command_here"}
OR if done or found vulnerability:
{"action": "finish", "report": "Detailed report of findings and ideas."}
Do NOT output markdown. ONLY valid JSON."""

messages = [{"role": "system", "content": system_prompt}]
context = f"User objective: {ISSUE_BODY}\nHistory:\n"

max_steps = 5
for step in range(max_steps):
    messages.append({"role": "user", "content": context + "\nWhat is your next step?"})
    
    try:
        payload = {"model": "qwen2.5-coder:7b", "messages": messages, "stream": False, "format": "json"}
        resp = requests.post("http://127.0.0.1:11434/api/chat", json=payload, timeout=300).json()
        ai_resp = json.loads(resp['message']['content'])
    except Exception as e:
        post_comment(f"❌ فشل النموذج: {e}")
        break

    if ai_resp.get("action") == "finish":
        post_comment(f"🏁 **التقرير النهائي:**\n\n{ai_resp.get('report')}")
        break
        
    cmd = ai_resp.get("command", "")
    post_comment(f"⚙️ **الخطوة {step+1}:**\n```bash\n{cmd}\n```\n⏳ *جاري التنفيذ...*")
    
    try:
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=300)
        out = result.stdout + result.stderr
        if len(out) > 3000: out = out[:3000] + "\n...[مختصر]"
    except subprocess.TimeoutExpired:
        out = "[انتهى الوقت - الأمر استغرق أكثر من 5 دقائق]"
    except Exception as e:
        out = str(e)
        
    post_comment(f"📊 **النتيجة:**\n```\n{out}\n```")
    context += f"\nStep {step+1}:\nCommand: {cmd}\nOutput: {out}\n"
    messages.append({"role": "assistant", "content": json.dumps(ai_resp)})
