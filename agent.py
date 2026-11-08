import os, requests, subprocess, json, re
from urllib.parse import urlparse

GITHUB_TOKEN = os.environ["GITHUB_TOKEN"]
ISSUE_NUM = os.environ["ISSUE_NUMBER"]
ISSUE_BODY = os.environ.get("ISSUE_BODY", "No instructions")
REPO = os.environ["REPO"]

def post_comment(msg):
    url = f"https://api.github.com/repos/{REPO}/issues/{ISSUE_NUM}/comments"
    headers = {"Authorization": f"token {GITHUB_TOKEN}", "Accept": "application/vnd.github.v3+json"}
    requests.post(url, headers=headers, json={"body": msg})

post_comment(f"🤖 **ZeroHunter (الهجوم المباشر):** استلمت الهدف `{ISSUE_BODY}`. سأقوم بتشغيل الترسانة كاملة الآن...")

# استخراج اسم النطاق فقط لـ Nmap
target = ISSUE_BODY.strip()
if "http" in target:
    parsed = urlparse(target)
    domain = parsed.netloc if parsed.netloc else parsed.path
else:
    domain = target

# 1. Nmap
post_comment(f"⚙️ **[1/3] فحص المنافذ والخدمات (Nmap) على {domain}...**")
try:
    nmap_cmd = f"nmap -sV -Pn --top-ports 100 {domain}"
    nmap_res = subprocess.run(nmap_cmd, shell=True, capture_output=True, text=True, timeout=120)
    nmap_out = nmap_res.stdout[:1500] # نأخذ جزء بسيط فقط لحماية الذاكرة
    post_comment(f"📊 **نتيجة Nmap:**\n```\n{nmap_out}\n```")
except Exception as e:
    nmap_out = "Nmap failed"
    post_comment(f"❌ فشل Nmap: {e}")

# 2. Nuclei
post_comment(f"⚙️ **[2/3] البحث عن الثغرات المعروفة (Nuclei) على {domain}...**")
try:
    nuclei_cmd = f"nuclei -u http://{domain} -silent -severity critical,high,medium"
    nuclei_res = subprocess.run(nuclei_cmd, shell=True, capture_output=True, text=True, timeout=180)
    nuclei_out = nuclei_res.stdout[:1500]
    if not nuclei_out.strip():
        nuclei_out = "لم يتم العثور على ثغرات معروفة عبر Nuclei."
    post_comment(f"📊 **نتيجة Nuclei:**\n```\n{nuclei_out}\n```")
except Exception as e:
    nuclei_out = "Nuclei failed"
    post_comment(f"❌ فشل Nuclei: {e}")

# 3. AI Analysis
post_comment(f"🧠 **[3/3] جاري تحليل النتائج بواسطة الذكاء الاصطناعي للبحث عن ثغرات...**")
system_prompt = "You are an elite cybersecurity analyst. Analyze the provided Nmap and Nuclei scan results. Write a clear report in Arabic explaining if any vulnerabilities were found, how dangerous they are, and how to fix them. If no vulnerabilities are found, state that clearly."
prompt = f"Target: {domain}\n\nNmap Results:\n{nmap_out}\n\nNuclei Results:\n{nuclei_out}\n\nWrite the final vulnerability report."

try:
    payload = {"model": "qwen2.5-coder:1.5b", "prompt": prompt, "system": system_prompt, "stream": False}
    resp = requests.post("http://127.0.0.1:11434/api/generate", json=payload, timeout=180).json()
    ai_report = resp.get('response', 'فشل توليد التقرير.')
    post_comment(f"🏁 **التقرير النهائي للذكاء الاصطناعي:**\n\n{ai_report}")
except Exception as e:
    post_comment(f"❌ فشل الاتصال بالذكاء الاصطناعي: {e}")
