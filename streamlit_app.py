import os
import re
import json
import time
import requests
import streamlit as st
from pathlib import Path
from core.scanner import safe_extract_zip, run_static_scan

st.set_page_config(page_title="ZeroHunter Interactive", page_icon="🛡️", layout="wide")
st.title("🛡️ ZeroHunter — الدردشة التفاعلية وفحص الملفات المضغوطة")

REPO = os.environ.get("GITHUB_REPO", "sdxdxa56-design/jdjsjsh")
github_token = st.secrets.get("GITHUB_TOKEN", os.environ.get("GITHUB_TOKEN", ""))

HEADERS = {
    "Authorization": f"token {github_token}",
    "Accept": "application/vnd.github.v3+json",
} if github_token else {}

UPLOAD_ROOT = Path("workspace/uploads/streamlit_session")
UPLOAD_ROOT.mkdir(parents=True, exist_ok=True)

if "messages" not in st.session_state:
    st.session_state.messages = []
if "active_issue" not in st.session_state:
    st.session_state.active_issue = None
if "seen_comments" not in st.session_state:
    st.session_state.seen_comments = set()
if "latest_status" not in st.session_state:
    st.session_state.latest_status = {"phase": "جاهز", "progress": 0, "eta_seconds": 0}
if "pending_zips" not in st.session_state:
    st.session_state.pending_zips = []
if "unpacked_files" not in st.session_state:
    st.session_state.unpacked_files = []


def sync_issue_comments() -> bool:
    issue_num = st.session_state.active_issue
    if not issue_num or not HEADERS:
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


# Sidebar: Upload ZIP archives or folder files directly into the workspace
with st.sidebar:
    st.subheader("📦 رفع ملف مضغوط أو مجلد")
    uploaded_items = st.file_uploader(
        "اختر ملف .zip أو عدة ملفات من مجلد",
        accept_multiple_files=True,
    )
    if uploaded_items:
        saved_names = []
        for uf in uploaded_items:
            safe_name = Path(uf.name).name
            dest = UPLOAD_ROOT / safe_name
            dest.write_bytes(uf.getbuffer())
            saved_names.append(safe_name)
            if safe_name.lower().endswith(".zip") and str(dest) not in st.session_state.pending_zips:
                st.session_state.pending_zips.append(str(dest))
            elif not safe_name.lower().endswith(".zip") and safe_name not in st.session_state.unpacked_files:
                st.session_state.unpacked_files.append(safe_name)
        st.success(f"تم حفظ {len(saved_names)} ملف. اكتب في الدردشة: «فككه» أو «افحصه».")

    if st.session_state.unpacked_files:
        st.caption(f"الملفات الجاهزة ({len(st.session_state.unpacked_files)}):")
        st.code("\n".join(st.session_state.unpacked_files[:30]))

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

prompt = st.chat_input("ارفع .zip ثم اكتب 'فككه'، أو تحدث مع ZeroHunter مباشرة...")
if prompt:
    st.session_state.messages.append({"role": "user", "content": prompt})

    # Local unpack command ("فككه") before talking/auditing (avoid matching substrings like "كيفك")
    if re.search(r"(?:^|[\s،,.:;!?؟«»'()-])(?:فككه|فكك|فك\s+الأرشيف|فك\s+الملف|استخرجه|استخرج|unzip|extract)(?:$|[\s،,.:;!?؟«»'()-])", prompt.lower()) and st.session_state.pending_zips:
        extracted_all = []
        for zpath in st.session_state.pending_zips:
            zp = Path(zpath)
            if zp.exists():
                extracted_all.extend(safe_extract_zip(zp, UPLOAD_ROOT / "extracted"))
        st.session_state.pending_zips = []
        st.session_state.unpacked_files.extend(extracted_all)
        local_findings = run_static_scan(UPLOAD_ROOT / "extracted")
        preview = "\n".join(f"- {x}" for x in extracted_all[:25]) or "لا توجد ملفات"
        findings_note = (
            "\n\n🔎 **نقاط اشتباه أولية رُصدت تلقائياً:**\n"
            + "\n".join(f"- `{f['file']}:{f['line']}`: {f['message']}" for f in local_findings[:8])
            if local_findings
            else ""
        )
        st.session_state.messages.append({
            "role": "assistant",
            "content": (
                f"📦 **تم فك الأرشيف بنجاح ({len(extracted_all)} ملفاً):**\n{preview}"
                f"{findings_note}\n\n💬 يمكنك الآن سؤالي عن أي ملف أو طلب الفحص الشامل والـ Fuzzing!"
            ),
        })
        st.rerun()
    elif st.session_state.active_issue and HEADERS:
        c_url = f"https://api.github.com/repos/{REPO}/issues/{st.session_state.active_issue}/comments"
        resp = requests.post(c_url, headers=HEADERS, json={"body": f"[USER_CMD] {prompt}"}, timeout=15)
        if resp.status_code != 201:
            st.error("تعذر إرسال التوجيه للوكيل.")
        st.rerun()
    elif HEADERS:
        context_prefix = ""
        if st.session_state.unpacked_files:
            context_prefix = f"[المسار المحلي: workspace/uploads/streamlit_session/extracted] "
        i_url = f"https://api.github.com/repos/{REPO}/issues"
        resp = requests.post(i_url, headers=HEADERS, json={"title": f"Audit: {prompt[:40]}", "body": context_prefix + prompt}, timeout=15)
        if resp.status_code != 201:
            st.error(f"فشل إنشاء المهمة ({resp.status_code}): {resp.text[:200]}")
        else:
            st.session_state.active_issue = resp.json()["number"]
            st.session_state.seen_comments = set()
            st.session_state.latest_status = {"phase": "بدء التشغيل", "progress": 5, "eta_seconds": 180}
            st.rerun()
    else:
        st.session_state.messages.append({
            "role": "assistant",
            "content": "⚠️ أضف GITHUB_TOKEN لإرسال المهام إلى Actions، أو استخدم web_app.py محلياً مع نموذج GGUF مباشرة بدون إنترنت.",
        })
        st.rerun()

if st.session_state.active_issue:
    time.sleep(4)
    st.rerun()
