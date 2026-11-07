import os, requests, subprocess, json, re

GITHUB_TOKEN = os.environ["GITHUB_TOKEN"]
ISSUE_NUM = os.environ["ISSUE_NUMBER"]
ISSUE_BODY = os.environ.get("ISSUE_BODY", "No instructions")
REPO = os.environ["REPO"]

def post_comment(msg):
    url = f"https://api.github.com/repos/{REPO}/issues/{ISSUE_NUM}/comments"
    headers = {"Authorization": f"token {GITHUB_TOKEN}", "Accept": "application/vnd.github.v3+json"}
    requests.post(url, headers=headers, json={"body": msg})

post_comment(f"🤖 **ZeroHunter (Jabar):** استلمت الهدف. سأبدأ خطة الهجوم الشاملة (Zero-Day Hunting)...")

system_prompt = """You are ZeroHunter Jabar, an elite autonomous zero-day hunter.
You have access to: nmap, nuclei, ffuf, sqlmap, semgrep, afl++, radamsa, clang, git, and standard Linux tools.
Your objective is to find vulnerabilities. You must think step-by-step.

PLAYBOOK:
1. If target is a SOURCE CODE (e.g., GitHub link): 
   -> git clone <url> 
   -> semgrep --config auto <dir>
   -> Look for memory bugs, write a harness, compile with clang -fsanitize=fuzzer,address, and run it.
2. If target is a WEB URL: 
   -> nuclei -u <url>
   -> ffuf -u <url>/FUZZ -w /usr/share/wordlists/dirb/common.txt
   -> Check for SQLi with sqlmap.
3. If target is an IP (Ngrok/Pinggy): -> nmap -sV <ip>
4. If you find a crash (ASan output) or a vulnerability, analyze it and explain it.

Reply with exactly ONE JSON object:
{"action": "run_command", "command": "bash_command_here"}
OR if you are done: {"action": "finish", "report": "Detailed report of findings."}
Do NOT output markdown. ONLY valid JSON."""

messages = [{"role": "system", "content": system_prompt}]
context = f"Target objective: {ISSUE_BODY}\nHistory:\n"

max_steps = 10 # 10 حلقات تفكير عميقة
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
        post_comment(f"🏁 **التقرير النهائي للثغرات:**\n\n{ai_resp.get('report')}")
        break
        
    cmd = ai_resp.get("command", "")
    post_comment(f"⚙️ **الخطوة {step+1}:**\n```bash\n{cmd}\n```\n⏳ *جاري التنفيذ...*")
    
    try:
        # استخدام مهلة 10 دقائق للسماح للفاحص بالعمل
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=600)
        out = result.stdout + result.stderr
        if len(out) > 4000: out = out[:4000] + "\n...[مختصر]"
    except subprocess.TimeoutExpired:
        out = "[انتهى الوقت - الأمر استغرق أكثر من 10 دقائق]"
    except Exception as e:
        out = str(e)
        
    post_comment(f"📊 **النتيجة:**\n```\n{out}\n```")
    context += f"\nStep {step+1}:\nCommand: {cmd}\nOutput: {out}\n"
    messages.append({"role": "assistant", "content": json.dumps(ai_resp)})
