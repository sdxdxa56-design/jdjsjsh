import os, requests, subprocess, json, re, sys

# التأكد من تثبيت مكتبة Hugging Face
try:
    from huggingface_hub import InferenceClient
except ImportError:
    subprocess.check_call([sys.executable, "-m", "pip", "install", "huggingface_hub"])
    from huggingface_hub import InferenceClient

GITHUB_TOKEN = os.environ["GITHUB_TOKEN"]
ISSUE_NUM = os.environ["ISSUE_NUMBER"]
ISSUE_BODY = os.environ.get("ISSUE_BODY", "No instructions")
REPO = os.environ["REPO"]
HF_TOKEN = os.environ.get("HF_TOKEN", "")

def post_comment(msg):
    url = f"https://api.github.com/repos/{REPO}/issues/{ISSUE_NUM}/comments"
    headers = {"Authorization": f"token {GITHUB_TOKEN}", "Accept": "application/vnd.github.v3+json"}
    requests.post(url, headers=headers, json={"body": msg})

post_comment(f"🤖 **ZeroHunter:** استلمت الهدف `{ISSUE_BODY}`. جاري التحليل...")

prompt = f"""You are ZeroHunter, an elite cybersecurity AI.
Analyze this target and provide a bash command to test it, or a report if a vulnerability is found.
Target: {ISSUE_BODY}
Reply ONLY with valid JSON: {{"action": "run_command", "command": "bash_command"}} OR {{"action": "finish", "report": "report details"}}."""

try:
    # تهيئة العميل (يدعم التوجيه التلقائي)
    client = InferenceClient(token=HF_TOKEN)
    ai_reply = ""
    
    try:
        # المحاولة الأولى: استخدام النموذج الخاص بك (المدرب)
        post_comment("⏳ جاري الاتصال بالنموذج المخصص...")
        completion = client.chat_completion(
            model="sdxdxa56/zerohunter-qwen-7b",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=250,
        )
        ai_reply = completion.choices[0].message.content
        
    except Exception as e:
        # إذا فشل النموذج المخصص بسبب الصلاحيات، نستخدم النموذج الأساسي
        if "403" in str(e) or "Forbidden" in str(e) or "permissions" in str(e):
            post_comment("⚠️ النموذج المخصص يتطلب صلاحيات مدفوعة في Hugging Face. سأقوم بالتبديل تلقائياً إلى النموذج الأساسي (Qwen 7B) لإكمال المهمة...")
            completion = client.chat_completion(
                model="Qwen/Qwen2.5-Coder-7B-Instruct", 
                messages=[{"role": "user", "content": prompt}],
                max_tokens=250,
            )
            ai_reply = completion.choices[0].message.content
        else:
            raise e

    # تنظيف الرد واستخراج الـ JSON
    json_match = re.search(r'\{.*\}', ai_reply, re.DOTALL)
    if json_match:
        ai_reply = json_match.group(0)
        
    ai_resp = json.loads(ai_reply)

    if ai_resp.get("action") == "finish":
        post_comment(f"🚨 **تقرير النموذج:**\n\n{ai_resp.get('report')}")
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
