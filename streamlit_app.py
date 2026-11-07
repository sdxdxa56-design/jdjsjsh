import streamlit as st
import requests
import time

st.set_page_config(page_title="ZeroHunter Jabar", page_icon="🛡️", layout="wide")
st.title("🛡️ ZeroHunter Jabar - Zero-Day Hunter")
st.markdown("""
**كيف تستخدم الوكيل؟**
*   **موقع ويب:** اكتب `Scan https://example.com with nuclei and ffuf`
*   **كود مصدري:** اكتب `Clone https://github.com/user/repo and fuzz it with semgrep and AFL`
*   **شبكة محلية (راوترك):** استخدم **Pinggy/Ngrok** للحصول على رابط عام، ثم أرسل الرابط للوكيل.
""")

REPO = "sdxdxa56-design/jdjsjsh"
github_token = st.secrets.get("GITHUB_TOKEN", "")

if not github_token:
    github_token = st.text_input("أدخل GitHub Token:", type="password")

if "messages" not in st.session_state:
    st.session_state.messages = []

for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

if prompt := st.chat_input("اكتب هدفك... (مثال: Clone cJSON and fuzz it)"):
    if not github_token:
        st.error("التوكن مطلوب!")
        st.stop()
    
    if len(prompt) < 10:
        st.warning("الرجاء كتابة هدف وطلب واضح (10 أحرف على الأقل).")
        st.stop()

    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        with st.spinner("جاري إرسال الهدف إلى خوادم GitHub..."):
            headers = {"Authorization": f"token {github_token}", "Accept": "application/vnd.github.v3+json"}
            url = f"https://api.github.com/repos/{REPO}/issues"
            payload = {"title": f"Zero-Day Target: {prompt[:30]}...", "body": prompt}
            resp = requests.post(url, headers=headers, json=payload)
            
            if resp.status_code != 201:
                st.error(f"فشل: {resp.text}")
                st.stop()
            
            issue_num = resp.json()["number"]
            status_box = st.empty()
            status_box.info(f"المهمة #{issue_num} قيد التنفيذ. الوكيل يفكر ويجرب (قد يأخذ 5-10 دقائق)...")
            
            final_reply = ""
            for _ in range(200): # الانتظار حتى 20 دقيقة
                time.sleep(6)
                c_url = f"https://api.github.com/repos/{REPO}/issues/{issue_num}/comments"
                c_resp = requests.get(c_url, headers=headers).json()
                comments = [c["body"] for c in c_resp]
                
                for c in comments:
                    if "🏁 **التقرير النهائي" in c:
                        final_reply = c
                        break
                    elif "❌ فشل النموذج" in c or "❌ خطأ:" in c:
                        final_reply = c
                        break
                if final_reply:
                    break
                    
                if comments:
                    status_box.info(f"⏳ حالة الوكيل: {comments[-1][:120]}...")
            
            status_box.empty()
            if final_reply:
                st.markdown(final_reply)
                st.session_state.messages.append({"role": "assistant", "content": final_reply})
            else:
                st.warning("استغرق الأمر وقتاً طويلاً. يرجى فتح GitHub Issues لمتابعة الحالة.")
                st.session_state.messages.append({"role": "assistant", "content": "تجاوز الوقت. راجع GitHub."})
