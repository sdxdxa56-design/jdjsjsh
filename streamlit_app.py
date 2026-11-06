import streamlit as st
import requests
import time

st.set_page_config(page_title="ZeroHunter AI", page_icon="🛡️")
st.title("🛡️ ZeroHunter Cloud Chat")
st.markdown("تحدث مع الذكاء الاصطناعي، وسيقوم هو بفحص الأنظمة في سيرفرات GitHub.")

# إعدادات GitHub
REPO = "sdxdxa56-design/jdjsjsh"

# قراءة التوكن من إعدادات Streamlit (Secrets) أو من المستخدم
github_token = st.secrets.get("GITHUB_TOKEN", "")
if not github_token:
    github_token = st.text_input("أدخل GitHub Token (بصلاحية repo):", type="password")

# ذاكرة الدردشة
if "messages" not in st.session_state:
    st.session_state.messages = []

# عرض الرسائل السابقة
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# مربع الإدخال
if prompt := st.chat_input("اكتب طلبك الأمني هنا (مثال: Fuzz cJSON library for 2 minutes)..."):
    if not github_token:
        st.error("الرجاء إدخال التوكن أولاً!")
        st.stop()

    # إضافة رسالة المستخدم
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    # التواصل مع GitHub
    with st.chat_message("assistant"):
        with st.spinner("جاري إرسال الطلب إلى GitHub Actions..."):
            headers = {"Authorization": f"token {github_token}", "Accept": "application/vnd.github.v3+json"}
            url = f"https://api.github.com/repos/{REPO}/issues"
            payload = {"title": f"Chat Request: {prompt[:30]}...", "body": prompt}
            resp = requests.post(url, headers=headers, json=payload)
            
            if resp.status_code != 201:
                st.error(f"فشل إنشاء الطلب: {resp.text}")
                st.stop()
            
            issue_num = resp.json()["number"]
            status_box = st.empty()
            status_box.info(f"تم إنشاء المهمة #{issue_num}. جاري تشغيل النموذج واكتشاف الثغرات (قد يأخذ دقيقتين)...")
            
            # الانتظار وسحب النتائج
            final_reply = ""
            for _ in range(60): # ننتظر حتى 3 دقائق
                time.sleep(3)
                c_url = f"https://api.github.com/repos/{REPO}/issues/{issue_num}/comments"
                c_resp = requests.get(c_url, headers=headers).json()
                comments = [c["body"] for c in c_resp]
                
                # هل انتهى الذكاء الاصطناعي؟
                for c in comments:
                    if "✅ **النتيجة:**" in c or "❌ خطأ:" in c:
                        final_reply = c
                        break
                if final_reply:
                    break
                    
                # تحديث الحالة للمستخدم
                if comments:
                    status_box.info(f"⏳ آخر تحديث: {comments[-1][:80]}...")
            
            status_box.empty()
            if final_reply:
                st.markdown(final_reply)
                st.session_state.messages.append({"role": "assistant", "content": final_reply})
            else:
                st.warning("استغرق الأمر وقتاً أطول. يرجى التحقق من تبويب Issues في مستودعك على GitHub.")
                st.session_state.messages.append({"role": "assistant", "content": "انتهى الوقت. يرجى التحقق من GitHub."})
