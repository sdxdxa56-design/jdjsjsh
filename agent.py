import os
import re
import json
import time
import requests
from pathlib import Path
from typing import Dict, Any, List, Optional
from huggingface_hub import hf_hub_download
from llama_cpp import Llama

from core.scanner import clone_or_prepare_workspace, run_static_scan, extract_target_context
from core.knowledge import lookup_online_knowledge
from modules.binary_fuzz import run_libfuzzer_on_target
from triage.analyzer import summarize_crash_for_llm, save_markdown_report


GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "")
HF_TOKEN = os.environ.get("HF_TOKEN") or None
ISSUE_NUM = os.environ.get("ISSUE_NUMBER", "0")
ISSUE_BODY = os.environ.get("ISSUE_BODY", "Audit local targets/demo.c")
REPO = os.environ.get("REPO", "sdxdxa56-design/jdjsjsh")
HF_REPO = os.environ.get("ZEROHUNTER_HF_REPO", "sdxdxa56/zerohunter-qwen-gguf")
GGUF_FILE = os.environ.get("ZEROHUNTER_GGUF_FILE", "zerohunter-3b-q4_k_m.gguf")
FUZZ_TIMEOUT = int(os.environ.get("FUZZ_TIMEOUT", "90"))

HEADERS = {
    "Authorization": f"token {GITHUB_TOKEN}",
    "Accept": "application/vnd.github.v3+json",
}

SEEN_USER_COMMENTS = set()


def post_comment(body: str) -> None:
    print(body)
    if not GITHUB_TOKEN or ISSUE_NUM == "0":
        return
    url = f"https://api.github.com/repos/{REPO}/issues/{ISSUE_NUM}/comments"
    requests.post(url, headers=HEADERS, json={"body": body}, timeout=20)


def post_status(phase: str, progress: int, eta_sec: int, msg_ar: str) -> None:
    payload = json.dumps({
        "phase": phase,
        "progress": progress,
        "eta_seconds": eta_sec,
        "message": msg_ar,
    }, ensure_ascii=False)
    post_comment(f"⏳ **[{progress}% | {phase}]** {msg_ar}\n<!-- ZEROHUNTER_STATUS:{payload} -->")


def is_audit_request(text: str) -> bool:
    """Detects whether the user wants code/repository auditing & fuzzing vs natural chat."""
    if re.search(r"https://github\.com/[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", text):
        return True
    if re.search(r"\.(c|cpp|h|py|js|ts|go|php|conf)\b", text):
        return True
    audit_keywords = ("افحص", "فحص", "ثغرات", "فازر", "audit", "fuzz", "scan", "targets/")
    return any(k in text.lower() for k in audit_keywords)


def poll_user_commands(llm: Optional[Llama], current_state: Dict[str, Any]) -> List[str]:
    """Reads live [USER_CMD] comments mid-run and responds naturally via the model."""
    if not GITHUB_TOKEN or ISSUE_NUM == "0":
        return []
    url = f"https://api.github.com/repos/{REPO}/issues/{ISSUE_NUM}/comments?per_page=100"
    resp = requests.get(url, headers=HEADERS, timeout=20)
    if resp.status_code != 200:
        return []
    new_directives: List[str] = []
    for c in resp.json():
        cid = c.get("id")
        body = c.get("body", "")
        if cid in SEEN_USER_COMMENTS:
            continue
        if "[USER_CMD]" in body:
            SEEN_USER_COMMENTS.add(cid)
            user_text = body.replace("[USER_CMD]", "").strip()
            new_directives.append(user_text)
            if llm is not None:
                live_reply = chatml_query(
                    llm,
                    "أنت ZeroHunter، مساعد أمني ذكي تتحدث العربية بطبيعية. أجب المستخدم بناءً على حالة الفحص الحالية واقترح خطة مختصرة.",
                    f"حالة الفحص الآن: المرحلة={current_state['phase']}, التقدم={current_state['progress']}%, "
                    f"الوقت المتبقي={current_state['eta']}ث, التفاصيل={current_state['detail']}, "
                    f"النتائج المكتشفة حتى الآن={current_state.get('findings_count', 0)}.\nسؤال/توجيه المستخدم: {user_text}",
                    max_tokens=280,
                )
                post_comment(f"💬 **رد ZeroHunter المباشر:**\n{live_reply}")
            else:
                post_comment(
                    f"📡 **رد حي:** المرحلة الحالية **{current_state['phase']}** ({current_state['progress']}%)، المتبقي ~{current_state['eta']}ث."
                )
    return new_directives


def chatml_query(llm: Llama, system_prompt: str, user_prompt: str, max_tokens: int = 512) -> str:
    prompt = (
        f"<|im_start|>system\n{system_prompt}<|im_end|>\n"
        f"<|im_start|>user\n{user_prompt}<|im_end|>\n"
        f"<|im_start|>assistant\n"
    )
    out = llm(prompt, max_tokens=max_tokens, stop=["<|im_end|>"], echo=False, temperature=0.2)
    return out["choices"][0]["text"].strip()


def load_model() -> Llama:
    model_file = hf_hub_download(
        repo_id=HF_REPO,
        filename=GGUF_FILE,
        token=HF_TOKEN,
    )
    return Llama(model_path=model_file, n_ctx=4096, n_threads=4, verbose=False)


def main() -> None:
    start_time = time.time()
    state: Dict[str, Any] = {
        "phase": "1/4 التهيئة",
        "progress": 5,
        "eta": 180,
        "detail": "تحميل النموذج وتجهيز الجلسة",
        "findings_count": 0,
    }
    post_status(state["phase"], state["progress"], state["eta"], state["detail"])

    try:
        llm = load_model()
    except Exception as exc:
        post_comment(f"❌ خطأ في تحميل النموذج من Hugging Face ({HF_REPO}/{GGUF_FILE}): {exc}")
        return

    # الوضع 1: محادثة طبيعية مع البحث الحي في قواعد المعرفة على الإنترنت
    if not is_audit_request(ISSUE_BODY):
        post_status("محادثة مباشرة", 50, 15, "البحث في مراجع الإنترنت وتوليد الرد")
        web_context = lookup_online_knowledge(ISSUE_BODY)
        reply = chatml_query(
            llm,
            "أنت ZeroHunter، مساعد ذكاء اصطناعي متخصص في أمن الكود واكتشاف الثغرات. تحدث بالعربية بطبيعية، واستفد من المراجع الحديثة المرفقة من الإنترنت لتقديم خطط وأفكار عملية.",
            f"سؤال المستخدم: {ISSUE_BODY}\n\nمراجع حديثة من قواعد الثغرات على الإنترنت:\n{web_context}",
            max_tokens=650,
        )
        post_comment(f"🏁 **التقرير النهائي**\n\n{reply}")
        return

    # الوضع 2: فحص الكود وعرض النتائج والخطط والأفكار أولاً بأول
    state = {"phase": "2/4 الاستكشاف الثابت", "progress": 25, "eta": 140, "detail": "فحص الكود بـ cppcheck وsemgrep", "findings_count": 0}
    post_status(state["phase"], state["progress"], state["eta"], state["detail"])
    target_dir = clone_or_prepare_workspace(ISSUE_BODY, Path("workspace"))
    findings = run_static_scan(target_dir)
    state["findings_count"] = len(findings)
    directives = poll_user_commands(llm, state)

    # عرض النتائج الفورية + خطط وأفكار من النموذج فور انتهاء الاستكشاف
    preview_list = "\n".join(
        f"- {f['file']}:{f['line']} ({f['tool']}) -> {f['message']}" for f in findings[:6]
    ) or "لا توجد أنماط خطرة واضحة في المسح الأولي."
    immediate_plan = chatml_query(
        llm,
        "أنت ZeroHunter. لخّص للمستخدم ما وجدته في هذه الخطوة فوراً بالعربية، واقترح خطة العمل والأفكار للخطوة القادمة في نقاط واضحة.",
        f"نتائج الاستكشاف الثابت ({len(findings)} نقطة):\n{preview_list}",
        max_tokens=320,
    )
    post_comment(
        f"🔎 **نتائج الاستكشاف الثابت الفورية ({len(findings)} نقطة):**\n{preview_list}\n\n"
        f"💡 **خطة وأفكار ZeroHunter للخطوة التالية:**\n{immediate_plan}"
    )

    report_sections: List[str] = [
        f"**الهدف:** `{ISSUE_BODY}`\n**الاستكشاف الثابت:** تم رصد {len(findings)} نقطة مشبوهة."
    ]

    # المرحلة 3: تجربة Fuzzing على أهم 3 ملفات C/C++ مكتشفة وعرض كل نتيجة فوراً
    c_findings = [f for f in findings if f["file"].endswith((".c", ".cpp"))][:3]
    if c_findings:
        for idx, top in enumerate(c_findings, start=1):
            pct = 45 + idx * 12
            state = {
                "phase": f"3/4 تجربة Fuzzing ({idx}/{len(c_findings)})",
                "progress": pct,
                "eta": FUZZ_TIMEOUT + 20,
                "detail": f"توليد Harness وتشغيل ASan على {top['file']}",
                "findings_count": len(findings),
            }
            post_status(state["phase"], state["progress"], state["eta"], state["detail"])

            snippet = extract_target_context(top["file"], top["line"])
            directive_note = f"\nتوجيه المستخدم: {'; '.join(directives)}" if directives else ""
            harness_prompt = (
                "Write ONLY valid C code implementing int LLVMFuzzerTestOneInput(const uint8_t *data, size_t size) "
                "to fuzz the target function shown below. Include <stdint.h> and <stddef.h>.\n"
                f"Target file: {top['file']}\n{snippet}{directive_note}"
            )
            raw_harness = chatml_query(llm, "You are ZeroHunter, a C/C++ fuzzing harness specialist.", harness_prompt, max_tokens=380)
            code_match = re.search(r"```(?:c|cpp)?\n(.*?)```", raw_harness, re.DOTALL)
            harness_code = code_match.group(1) if code_match else raw_harness

            fuzz_res = run_libfuzzer_on_target(top["file"], harness_code, timeout_sec=FUZZ_TIMEOUT)
            directives.extend(poll_user_commands(llm, state))

            if fuzz_res["crashed"]:
                triage_input = summarize_crash_for_llm(fuzz_res["asan_log"], snippet)
                analysis = chatml_query(
                    llm,
                    "أنت ZeroHunter. اشرح سبب هذا الانهيار المؤكد (ASan Crash) بالعربية الفصحى، واقترح التصحيح الآمن وأفكاراً لمنع تكراره.",
                    triage_input,
                    max_tokens=480,
                )
                msg_block = (
                    f"🚨 **اكتشاف فوري — ثغرة مؤكدة في `{top['file']}` (سطر {top['line']})**\n"
                    f"- **ملف الإثبات (PoC):** `{fuzz_res['crash_file']}`\n\n{analysis}"
                )
                post_comment(msg_block)
                report_sections.append(msg_block)
            else:
                ok_msg = f"🛡️ **نتيجة فحص `{top['file']}`:** صمد الفازر لمدة {FUZZ_TIMEOUT} ثانية دون انهيار ذاكرة."
                post_comment(ok_msg)
                report_sections.append(ok_msg)
    elif findings:
        state = {"phase": "4/4 التحليل النهائي", "progress": 82, "eta": 20, "detail": "تحليل النتائج واقتراح الخطط", "findings_count": len(findings)}
        post_status(state["phase"], state["progress"], state["eta"], state["detail"])
        summary_text = json.dumps(findings[:8], ensure_ascii=False, indent=2)
        analysis = chatml_query(
            llm,
            "أنت ZeroHunter. حلل هذه النتائج بالعربية، استبعد التنبيهات الكاذبة، واقترح خطة إصلاح وأفكار تحسين شاملة.",
            summary_text,
            max_tokens=550,
        )
        report_sections.append(analysis)
    else:
        report_sections.append("لم يتم العثور على أنماط خطرة واضحة في المسار المحدد.")

    elapsed = int(time.time() - start_time)
    save_markdown_report("ZeroHunter Security Audit Report", report_sections)
    final_body = "\n\n".join(report_sections)
    post_comment(f"🏁 **التقرير النهائي** (استغرق {elapsed} ثانية)\n\n{final_body}")


if __name__ == "__main__":
    main()
