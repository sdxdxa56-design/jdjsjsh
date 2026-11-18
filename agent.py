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


def poll_user_commands(llm: Optional[Llama], current_state: Dict[str, Any]) -> List[str]:
    """Reads live [USER_CMD] comments from the owner mid-run and answers status queries immediately."""
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
            if any(k in user_text for k in ("وصلت", "باقي", "حالة", "progress", "eta", "status")):
                post_comment(
                    f"📡 **رد حي على سؤالك:** أنا حالياً في **{current_state['phase']}** "
                    f"(التقدم: **{current_state['progress']}%**، الوقت المتبقي التقريبي: **{current_state['eta']} ثانية**). "
                    f"الخطوة الجارية: {current_state['detail']}"
                )
            else:
                new_directives.append(user_text)
                post_comment(f"🧭 استلمت توجيهك وسأدمجه في الخطوة الحالية: `{user_text}`")
    return new_directives


def chatml_query(llm: Llama, system_prompt: str, user_prompt: str, max_tokens: int = 512) -> str:
    prompt = (
        f"<|im_start|>system\n{system_prompt}<|im_end|>\n"
        f"<|im_start|>user\n{user_prompt}<|im_end|>\n"
        f"<|im_start|>assistant\n"
    )
    out = llm(prompt, max_tokens=max_tokens, stop=["<|im_end|>"], echo=False, temperature=0.1)
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
    state = {"phase": "1/4 التهيئة", "progress": 5, "eta": 180, "detail": "تحميل النموذج وتجهيز بيئة الفحص"}
    post_status(state["phase"], state["progress"], state["eta"], state["detail"])

    try:
        llm = load_model()
    except Exception as exc:
        post_comment(f"❌ خطأ في تحميل النموذج من Hugging Face ({HF_REPO}/{GGUF_FILE}): {exc}")
        return

    # Phase 1: Target Preparation & SAST
    state = {"phase": "2/4 الاستكشاف الثابت", "progress": 25, "eta": 140, "detail": "فحص الكود بـ cppcheck وsemgrep"}
    post_status(state["phase"], state["progress"], state["eta"], state["detail"])
    target_dir = clone_or_prepare_workspace(ISSUE_BODY, Path("workspace"))
    findings = run_static_scan(target_dir)
    directives = poll_user_commands(llm, state)

    report_sections: List[str] = []
    report_sections.append(f"**الهدف:** `{ISSUE_BODY}`\n**نتائج التحليل الثابت (SAST):** تم رصد {len(findings)} نقطة مشبوهة.")

    # Phase 2 & 3: Prioritize C/C++ files for LibFuzzer + ASan verification
    c_findings = [f for f in findings if f["file"].endswith((".c", ".cpp"))]
    if c_findings:
        top = c_findings[0]
        state = {"phase": "3/4 توليد الفازر والتجربة", "progress": 55, "eta": FUZZ_TIMEOUT + 30, "detail": f"توليد Harness لـ {top['file']}"}
        post_status(state["phase"], state["progress"], state["eta"], state["detail"])

        snippet = extract_target_context(top["file"], top["line"])
        directive_note = f"\nUser steering note: {'; '.join(directives)}" if directives else ""
        harness_prompt = (
            "Write ONLY valid C code implementing int LLVMFuzzerTestOneInput(const uint8_t *data, size_t size) "
            "to fuzz the target function shown below. Include <stdint.h> and <stddef.h>.\n"
            f"Target file: {top['file']}\n{snippet}{directive_note}"
        )
        raw_harness = chatml_query(llm, "You are ZeroHunter, a C/C++ fuzzing harness specialist.", harness_prompt, max_tokens=380)
        code_match = re.search(r"```(?:c|cpp)?\n(.*?)```", raw_harness, re.DOTALL)
        harness_code = code_match.group(1) if code_match else raw_harness

        fuzz_res = run_libfuzzer_on_target(top["file"], harness_code, timeout_sec=FUZZ_TIMEOUT)
        poll_user_commands(llm, state)

        if fuzz_res["crashed"]:
            state = {"phase": "4/4 فرز الانهيار", "progress": 85, "eta": 20, "detail": "تحليل أثر ASan وصياغة التصحيح"}
            post_status(state["phase"], state["progress"], state["eta"], state["detail"])
            triage_input = summarize_crash_for_llm(fuzz_res["asan_log"], snippet)
            analysis = chatml_query(
                llm,
                "You are ZeroHunter. Explain the root cause of this confirmed ASan crash in Arabic and provide a safe C patch.",
                triage_input,
                max_tokens=500,
            )
            report_sections.append(
                f"### 🚨 ثغرة مؤكدة (Confirmed ASan Crash)\n"
                f"- **الملف:** `{top['file']}` (السطر {top['line']})\n"
                f"- **ملف الإثبات (PoC):** `{fuzz_res['crash_file']}`\n\n"
                f"{analysis}"
            )
        else:
            report_sections.append(f"تم تشغيل LibFuzzer على `{top['file']}` لمدة {FUZZ_TIMEOUT} ثانية دون انهيار حرج.")
    elif findings:
        state = {"phase": "4/4 التحليل النهائي", "progress": 80, "eta": 25, "detail": "مراجعة نتائج SAST للنقاط المكتشفة"}
        post_status(state["phase"], state["progress"], state["eta"], state["detail"])
        summary_text = json.dumps(findings[:8], ensure_ascii=False, indent=2)
        analysis = chatml_query(
            llm,
            "You are ZeroHunter. Analyze these static findings in Arabic, filter false positives, and suggest fixes.",
            summary_text,
            max_tokens=500,
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
