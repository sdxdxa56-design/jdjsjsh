import streamlit as st
import requests
import time

st.set_page_config(page_title="ZeroHunter Fast", page_icon="⚡", layout="wide")
st.title("⚡ ZeroHunter Fast - Live Hacking")

REPO = "sdxdxa56-design/jdjsjsh"
github_token = st.secrets.get("GITHUB_TOKEN", "")
if not github_token:
    github_token = st.text_input("أدخل GitHub Token:", type="password")

if "messages" not in st.session_state:
    st.session_state.messages = []

for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

if prompt := st.chat_input("اكتب هدفك (مثال: Scan example.com with nuclei)"):
    if not github_token or len(prompt) < 5: st.stop()

    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        # إنشاء الـ Issue
        headers = {"Authorization": f"token {github_token}", "Accept": "application/vnd.github.v3+json"}
        url = f"https://api.github.com/repos/{REPO}/issues"
        resp = requests.post(url, headers=headers, json={"title": f"Target: {prompt[:20]}", "body": prompt})
        
        if resp.status_code != 201:
            st.error("فشل الاتصال بـ GitHub")
            st.stop()
            
        issue_num = resp.json()["number"]
        st.info(f"المهمة #{issue_num} بدأت. سيتم عرض الخطوات مباشرة هنا...")
        
        # صندوق ديناميكي لعرض الخطوات
        log_box = st.empty()
        full_log = ""
        
        # الانتظار وسحب التعليقات بشكل مستمر (Live)
        seen_comments = set()
        finished = False
        
        for _ in range(100): # مهلة 10 دقائق
            time.sleep(4) # فحص كل 4 ثوانٍ
            c_url = f"https://api.github.com/repos/{REPO}/issues/{issue_num}/comments"
            c_resp = requests.get(c_url, headers=headers).json()
            
            for c in c_resp:
                c_id = c["id"]
                if c_id not in seen_comments:
                    seen_comments.add(c_id)
                    body = c["body"]
                    full_log += body + "\n\n---\n\n"
                    log_box.markdown(full_log) # تحديث الشاشة فوراً
                    
                    if "🏁 **التقرير النهائي" in body or "❌" in body:
                        finished = True
            
            if finished: break

        if finished:
            st.session_state.messages.append({"role": "assistant", "content": full_log})
        else:
            st.warning("استغرق وقتاً طويلاً، راجع GitHub Issues.")
