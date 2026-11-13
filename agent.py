import os, subprocess, sys, json, re, requests
from huggingface_hub import snapshot_download

# 1. تثبيت مكتبات النموذج
try:
    import llama_cpp
except ImportError:
    print("جاري تثبيت llama-cpp-python...")
    subprocess.check_call([sys.executable, "-m", "pip", "install", "llama-cpp-python", "huggingface_hub"])

from llama_cpp import Llama
from huggingface_hub import snapshot_download

GITHUB_TOKEN = os.environ["GITHUB_TOKEN"]
ISSUE_NUM = os.environ["ISSUE_NUMBER"]
ISSUE_BODY = os.environ.get("ISSUE_BODY", "No instructions")
REPO = os.environ["REPO"]

def post_comment(msg):
    url = f"https://api.github.com/repos/{REPO}/issues/{ISSUE_NUM}/comments"
    headers = {"Authorization": f"token {GITHUB_TOKEN}", "Accept": "application/vnd.github.v3+json"}
    requests.post(url, headers=headers, json={"body": msg})

post_comment(f"🤖 **ZeroHunter (نموذجك الخاص 100%):** استلمت الهدف `{ISSUE_BODY}`. جاري تحميل النموذج وتطبيق LoRA...")

# 2. تحميل نموذجك (LoRA) من Hugging Face
post_comment("⏳ جاري تحميل نموذجك المدرب (LoRA)...")
lora_dir = "./my_lora"
snapshot_download(repo_id="sdxdxa56/zerohunter-qwen-7b", local_dir=lora_dir)

# 3. تحميل النموذج الأساسي بصيغة GGUF (خفيف جداً)
post_comment("⏳ جاري تحميل النموذج الأساسي (GGUF)...")
model_path = snapshot_download(
    repo_id="Qwen/Qwen2.5-Coder-7B-Instruct-GGUF",
    allow_patterns="*q4_k_m.gguf" # تحميل النسخة المكممة لتوفير الذاكرة
)

# 4. تشغيل النموذج ودمج LoRA
post_comment("⚙️ جاري تشغيل النموذج ودمج الأوزان...")
llm = Llama(
    model_path=model_path,
    lora_path=lora_dir, # هنا يتم تطبيق نموذجك الخاص
    n_ctx=2048,
    n_threads=4,
    verbose=False
)

# 5. التوجيه للنموذج
prompt = f"""You are ZeroHunter, an elite cybersecurity AI.
Analyze this target and provide a bash command to test it, or a report if a vulnerability is found.
Target: {ISSUE_BODY}
Reply ONLY with valid JSON: {{"action": "run_command", "command": "bash_command"}} OR {{"action": "finish", "report": "report details"}}."""

post_comment("🧠 النموذج يفكر الآن (قد يستغرق دقيقة لأن المعالج CPU)...")
output = llm(
    prompt,
    max_tokens=250,
    stop=["User:", "System:"],
    echo=False
)

ai_reply = output['choices'][0]['text'].strip()

try:
    # استخراج الـ JSON
    json_match = re.search(r'\{.*\}', ai_reply, re.DOTALL)
    if json_match:
        ai_reply = json_match.group(0)
        
    ai_resp = json.loads(ai_reply)

    if ai_resp.get("action") == "finish":
        post_comment(f"🚨 **تقرير النموذج الخاص بك:**\n\n{ai_resp.get('report')}")
    else:
        cmd = ai_resp.get("command")
        post_comment(f"⚙️ **الأمر المستخرج:**\n```bash\n{cmd}\n```\n⏳ *جاري التنفيذ...*")
        result_cmd = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=300)
        out = result_cmd.stdout + result_cmd.stderr
        if len(out) > 1500: out = out[:1500] + "\n...[مختصر]"
        post_comment(f"📊 **النتيجة:**\n```\n{out}\n```")

except json.JSONDecodeError:
    post_comment(f"❌ النموذج أرجع رداً غير صالح (ليس JSON):\n```\n{ai_reply}\n```")
except Exception as e:
    post_comment(f"❌ خطأ في التنفيذ: {e}")