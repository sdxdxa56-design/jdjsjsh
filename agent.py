import os, requests, subprocess, json, re, time

GITHUB_TOKEN = os.environ["GITHUB_TOKEN"]
ISSUE_NUM = os.environ["ISSUE_NUMBER"]
ISSUE_BODY = os.environ.get("ISSUE_BODY", "No instructions")
REPO = os.environ["REPO"]

def post_comment(msg):
    url = f"https://api.github.com/repos/{REPO}/issues/{ISSUE_NUM}/comments"
    headers = {"Authorization": f"token {GITHUB_TOKEN}", "Accept": "application/vnd.github.v3+json"}
    requests.post(url, headers=headers, json={"body": msg})

post_comment(f"🤖 **ZeroHunter (Zero-Day Hunter):** استلمت الهدف `{ISSUE_BODY}`. سأبدأ خطة الهجوم الشاملة (8 خطوات) للبحث عن ثغرات حقيقية...")

system_prompt = """You are ZeroHunter, an elite autonomous zero-day hunter.
Your goal: Find vulnerabilities. Do not stop unless you find something or finish 8 steps.
Tools available: nmap, nuclei, ffuf, sqlmap, gobuster, semgrep, clang.
Rules:
1. Web target: nmap -> nuclei (-silent) -> ffuf -> sqlmap (if parameters found).
2. Source code target: git clone -> semgrep -> compile -> AFL fuzzing.
3. After EVERY command, analyze the output.
4. If you find a vulnerability (e.g., SQLi, XSS, crash), you MUST set action to "finish" and write a detailed report explaining: the vulnerability type, the exact payload, how to exploit it, and how to fix it.

Reply EXACTLY ONE JSON: {"action": "run_command", "command": "bash_command"} OR {"action": "finish", "report": "Detailed Vulnerability Report"}
Do NOT output markdown. ONLY valid JSON."""

# دالة للاتصال بالنموذج مع إعادة المحاولة
def ask_ollama(messages):
    for attempt in range(3):
        try:
            payload = {"model": "qwen2.5-coder:1.5b", "messages": messages, "stream": False, "format": "json"}
            resp = requests.post("http://127.0.0.1:11434/api/chat", json=payload, timeout=180).json()
            return json.loads(resp['message']['content'])
        except Exception:
            time.sleep(5)
    return {"action": "finish", "report": "فشل الاتصال بالنموذج بسبب نفاد الذاكرة. يرجى مراجعة النتائج السابقة."}

messages = [{"role": "system", "content": system_prompt}]
context = f"Target: {ISSUE_BODY}\nHistory of actions:\n"

max_steps = 8 # 8 محاولات عميقة
for step in range(max_steps):
    messages.append({"role": "user", "content": context + "\nWhat is your next step?"})
    
    ai_resp = ask_ollama(messages)

    if ai_resp.get("action") == "finish":
        post_comment(f"🚨 **تم اكتشاف ثغرة / تقرير نهائي!**\n\n{ai_resp.get('report')}")
        break
        
    cmd = ai_resp.get("command", "")
    
    # تصحيح تلقائي للأوامر
    if "nmap" in cmd:
        cmd = cmd.replace("https://", "").replace("http://", "").replace("nmap -sV", "nmap -sV -Pn")
    if "nuclei" in cmd and "-silent" not in cmd:
        cmd += " -silent"
        
    post_comment(f"⚙️ **الخطوة {step+1}:**\n```bash\n{cmd}\n```\n⏳ *جاري التنفيذ...*")
    
    try:
        # نوجه المخرجات لملف لتجنب انهيار الذاكرة، ثم نقرأ 800 حرف فقط
        result = subprocess.run(f"{cmd} > out.txt 2>&1", shell=True, timeout=300)
        with open("out.txt", "r", errors="ignore") as f:
            out = f.read(800) # قراءة أول 800 حرف فقط
        
        if not out.strip(): out = "[تم التنفيذ بنجاح، لا توجد مخرجات]"
    except subprocess.TimeoutExpired:
        out = "[انتهى الوقت - استغرق الأمر أكثر من 5 دقائق]"
    except Exception as e:
        out = str(e)
        
    post_comment(f"📊 **النتيجة:**\n```\n{out}\n```")
    context += f"\nStep {step+1}:\nCommand: {cmd}\nOutput: {out}\n"
    messages.append({"role": "assistant", "content": json.dumps(ai_resp)})
