import os
import re
import json
import time
import requests
import streamlit as st

st.set_page_config(page_title="ZeroHunter Interactive", page_icon="🛡️", layout="wide")
st.title("🛡️ ZeroHunter — الوكيل الأمني التفاعلي")

REPO = os.environ.get("GITHUB_REPO", "sdxdxa56-design/jdjsjsh")
github_token = st.secrets.get("GITHUB_TOKEN", os.environ.get("GITHUB_TOKEN", ""))

if not github_token:
    st.warning("أضف GITHUB_TOKEN داخل Streamlit Secrets أو كمتغير بيئة لتفعيل الاتصال الآمن.")
    st.stop()

HEADERS = {
    "Authorization": f"token {github_token}",
    "Accept": "application/vnd.github.v3+json",
}

if "messages" not in st.session_state:
    st.session_state.messages = []
if "active_issue" not in st.session_state:
    st.session_state.active_issue = None
if "seen_comments" not in st.session_state:
    st.session_state.seen_comments = set()
if "latest_status" not in st.session_state:
    st.session_state.latest_status = {"phase": "جاهز", "progress": 0, "eta_seconds": 0}


def sync_issue_comments() -> bool:
    issue_num = st.session_state.active_issue
    if not issue_num:
        return False
    url = f"https://api.github.com/repos/{REPO}/issues/{issue_num}/comments?per_page=100"
    resp = requests.get(url, headers=HEADERS, timeout=15)
    if resp.status_code != 200:
        st.error(f"خطأ من GitHub API ({resp.status_code}): {resp.text[:200]}")
        return False

    finished = False
    for c in resp.json():
        cid = c.get("id")
        body = c.get("body", "")
        if cid in st.session_state.seen_comments:
            continue
        st.session_state.seen_comments.add(cid)

        status_match = re.search(r"<!-- ZEROHUNTER_STATUS:(.*?) -->", body)
        if status_match:
            try:
                st.session_state.latest_status = json.loads(status_match.group(1))
            except json.JSONDecodeError:
                pass

        if "[USER_CMD]" not in body:
            clean_body = re.sub(r"<!-- ZEROHUNTER_STATUS:.*? -->", "", body).strip()
            st.session_state.messages.append({"role": "assistant", "content": clean_body})

        if "🏁 **التقرير النهائي**" in body or body.startswith("❌"):
            finished = True

    if finished:
        st.session_state.active_issue = None
    return finished


# Top live progress bar when a task is active
if st.session_state.active_issue:
    sync_issue_comments()
    status = st.session_state.latest_status
    col1, col2, col3 = st.columns([3, 1, 1])
    with col1:
        st.progress(min(100, int(status.get("progress", 0))) / 100)
    with col2:
        st.metric("المرحلة", status.get("phase", "قيد التنفيذ"))
    with col3:
        st.metric("المتبقي تقريباً", f"{status.get('eta_seconds', 0)} ث")

for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

prompt = st.chat_input("أرسل هدفاً جديداً، أو اسأل الوكيل أثناء عمله (مثلاً: أين وصلت وكم باقي لك؟)")
if prompt:
    st.session_state.messages.append({"role": "user", "content": prompt})
    if st.session_state.active_issue:
        # Live two-way chat while the scan is still running
        c_url = f"https://api.github.com/repos/{REPO}/issues/{st.session_state.active_issue}/comments"
        resp = requests.post(c_url, headers=HEADERS, json={"body": f"[USER_CMD] {prompt}"}, timeout=15)
        if resp.status_code != 201:
            st.error("تعذر إرسال التوجيه للوكيل.")
        st.rerun()
    else:
        # Start a new audit issue
        i_url = f"https://api.github.com/repos/{REPO}/issues"
        resp = requests.post(i_url, headers=HEADERS, json={"title": f"Audit: {prompt[:40]}", "body": prompt}, timeout=15)
        if resp.status_code != 201:
            st.error(f"فشل إنشاء المهمة ({resp.status_code}): {resp.text[:200]}")
        else:
            st.session_state.active_issue = resp.json()["number"]
            st.session_state.seen_comments = set()
            st.session_state.latest_status = {"phase": "بدء التشغيل", "progress": 5, "eta_seconds": 180}
            st.rerun()

if st.session_state.active_issue:
    time.sleep(4)
    st.rerun()
