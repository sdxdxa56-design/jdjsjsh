import json
from pathlib import Path
import streamlit as st
from swarm10.registry import BASE_MODEL_ID, SWARM_AGENTS
from swarm10.operations_room import Swarm10OperationsRoom

st.set_page_config(page_title="ZeroHunter Swarm-10", page_icon="🛡️", layout="wide")
st.title("🛡️ غرفة عمليات السرب الذكي — 10 وكلاء (0.5B + LoRA)")
st.caption(f"النموذج الأساسي: {BASE_MODEL_ID} | الذاكرة المقدرة في GitHub Actions: 3.2GB / 7GB")

if "swarm10_board" not in st.session_state:
    st.session_state.swarm10_board = []

prompt = st.text_input("اكتب مهمة الفحص للوكلاء العشرة:", "افحص هذا الهدف واكتشف الثغرات واكتب رقعة الإصلاح")
col1, col2 = st.columns([1, 1])
with col1:
    use_dry = st.checkbox("وضع الفحص السريع (Dry-Run بدون تحميل أوزان ثقيلة)", value=True)
with col2:
    run_btn = st.button("تشغيل السرب من الوكيل 1 إلى الوكيل 10", type="primary")

if run_btn and prompt.strip():
    room = Swarm10OperationsRoom(dry_run=use_dry)
    res = room.run_pipeline(prompt.strip(), publish_issue=False)
    st.session_state.swarm10_board = res["board"]

tabs = st.tabs(["💬 غرفة المحادثة الجماعية"] + [f"{a['index']}. {a['arabic_role']}" for a in SWARM_AGENTS])

with tabs[0]:
    if not st.session_state.swarm10_board:
        st.info("اضغط زر التشغيل لبدء الحوار التتابعي بين الوكلاء العشرة.")
    for item in st.session_state.swarm10_board:
        with st.chat_message("assistant"):
            st.markdown(f"**الوكيل {item['index']} ({item['role']}):** {item['message']}")

for idx, agent in enumerate(SWARM_AGENTS, start=1):
    with tabs[idx]:
        st.subheader(f"الوكيل {agent['index']}: {agent['arabic_role']} ({agent['english_role']})")
        st.write(agent["specialty"])
        adapter_dir = Path("lora_adapters") / agent["folder"]
        st.write("حالة محول LoRA:", "✅ متوفر" if (adapter_dir / "adapter_config.json").exists() else "⏳ بانتظار التدريب على Colab")
        matching = [b for b in st.session_state.swarm10_board if b["agent_id"] == agent["id"]]
        if matching:
            st.success(matching[0]["message"])
        st.json({"tools": agent["tools"], "examples": agent["examples"]})
