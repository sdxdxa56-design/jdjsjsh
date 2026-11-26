import os
import json
import inspect
from pathlib import Path
from datasets import Dataset, concatenate_datasets, load_dataset
from unsloth import FastLanguageModel, is_bfloat16_supported
from trl import SFTTrainer
from transformers import TrainingArguments

try:
    from trl import SFTConfig
except ImportError:
    SFTConfig = None

MAX_SEQ_LENGTH = 8192
BASE_MODEL = "unsloth/Qwen2.5-Coder-7B-Instruct-bnb-4bit"
QUANT_METHOD = "q5_k_m"
OUTPUT_GGUF_DIR = os.environ.get("ZEROHUNTER_OUT_DIR", "./zerohunter_gguf")

# نسب المسارات الأربعة المعتمدة:
# 1) Memory/C++ (35%)  2) Web/APIs (70%)
# 3) Servers/Configs (10%)  4) Agent Tool-Calling & Arabic Status (15%)

print("1. Loading base model:", BASE_MODEL)
model, tokenizer = FastLanguageModel.from_pretrained(
    model_name=BASE_MODEL,
    max_seq_length=MAX_SEQ_LENGTH,
    dtype=None,
    load_in_4bit=True,
)

model = FastLanguageModel.get_peft_model(
    model,
    r=32,
    target_modules=["q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"],
    lora_alpha=64,
    lora_dropout=0,
    bias="none",
    use_gradient_checkpointing="unsloth",
    random_state=3407,
)

# أمثلة تأسيسية للمسارات الأربعة + صيغة المحادثة الحية
CORE_CONVERSATIONS = [
    {"conversations": [
        {"role": "system", "content": "You are ZeroHunter, a C/C++ fuzzing harness specialist."},
        {"role": "user", "content": "Write ONLY valid C code implementing LLVMFuzzerTestOneInput for:\nint parse(const uint8_t *d, size_t s);"},
        {"role": "assistant", "content": "```c\n#include <stdint.h>\n#include <stddef.h>\nint parse(const uint8_t *d, size_t s);\nint LLVMFuzzerTestOneInput(const uint8_t *data, size_t size) {\n    parse(data, size);\n    return 0;\n}\n```"},
    ]},
    {"conversations": [
        {"role": "system", "content": "You are ZeroHunter. Explain confirmed ASan crashes in Arabic and provide a safe patch."},
        {"role": "user", "content": "ASan Trace: ERROR: AddressSanitizer: stack-buffer-overflow on memcpy(e, d+2, len) where uint8_t e[32]."},
        {"role": "assistant", "content": "السبب الجذري: دالة memcpy تنسخ len بايت (قد يصل إلى 255) داخل مصفوفة ثابتة بحجم 32 بايت دون فحص الحد الأقصى.\nالإصلاح الآمن: أضف الشرط `if (len > sizeof(e)) return -1;` قبل النسخ."},
    ]},
    {"conversations": [
        {"role": "system", "content": "You are ZeroHunter. Analyze static findings in Arabic, filter false positives, and suggest fixes."},
        {"role": "user", "content": "Finding: subprocess.check_output(f'convert {user_fmt}', shell=True)"},
        {"role": "assistant", "content": "ثغرة مؤكدة (Command Injection): تمرير مدخلات المستخدم إلى shell=True يسمح بتنفيذ أوامر نظام.\nالإصلاح: مرّر قائمة معاملات `['convert', user_fmt]` واضبط `shell=False`."},
    ]},
    {"conversations": [
        {"role": "system", "content": "You are ZeroHunter. Audit server and container configurations for security flaws."},
        {"role": "user", "content": "nginx.conf: location /uploads/ { autoindex on; }"},
        {"role": "assistant", "content": "ملاحظة أمان (Directory Listing): تفعيل autoindex يكشف محتويات مجلد الرفع.\nالإصلاح: غيّر الإعداد إلى `autoindex off;` وأضف `server_tokens off;`."},
    ]},
    {"conversations": [
        {"role": "system", "content": "أنت ZeroHunter، مساعد ذكاء اصطناعي متخصص في أمن الكود. تحدث بالعربية بطبيعية واقترح خططاً وأفكاراً."},
        {"role": "user", "content": "مرحباً، كيف تستطيع مساعدتي اليوم في تأمين مشروعي؟"},
        {"role": "assistant", "content": "أهلاً بك! أستطيع التحاور معك حول تصميم الأمان، مراجعة الشيفرات المصدرية في مختلف اللغات، تشغيل فحوصات SAST و LibFuzzer، وعرض النتائج عليك خطوة بخطوة مع خطط إصلاح واضحة. أرسل لي الكود أو رابط المستودع لنبدأ، أو اسألني أي سؤال!"},
    ]},
    {"conversations": [
        {"role": "system", "content": "أنت ZeroHunter. لخّص للمستخدم ما وجدته في هذه الخطوة فوراً بالعربية، واقترح خطة العمل والأفكار للخطوة القادمة."},
        {"role": "user", "content": "نتائج الاستكشاف الثابت (2 نقطة):\n- targets/demo.c:8 -> Risky memcpy\n- server/api.py:14 -> subprocess shell=True"},
        {"role": "assistant", "content": "🔎 **النتائج الفورية:** رصدت نقطتين عاليتي الخطورة؛ الأولى نسخ ذاكرة غير مقيد في `targets/demo.c`، والثانية تنفيذ أوامر عبر `shell=True` في `server/api.py`.\n💡 **الخطط والأفكار للخطوة التالية:**\n1. توليد Harness فوري لملف `demo.c` وتشغيل `libFuzzer + ASan` لإثبات الثغرة عملياً.\n2. مراجعة مسار المدخلات في `api.py` واستبدال الأمر النصي بمصفوفة معاملات آمنة."},
    ]},
    {"conversations": [
        {"role": "system", "content": "أنت ZeroHunter Strategist، خبير أمني كبير بخبرة 20 عاماً تقود عمليات التقييم الأمني وتفصل الثغرات المؤكدة عن الإنذارات الكاذبة."},
        {"role": "user", "content": "رصدت الأداة 3 ملاحظات: 1) WebAPK MainActivity exported=true مع BROWSABLE 2) memcpy غير مقيدة مع ASan crash 3) استعلام SQL بـ PreparedStatement."},
        {"role": "assistant", "content": "### الملخص التنفيذي\nتم فرز نتائج الفحص واستبعاد الإنذارات الكاذبة؛ توجد ثغرة واحدة حرجة مؤكدة في الذاكرة.\n\n### أولاً: الثغرات المؤكدة بالدليل\n- **Buffer Overflow في memcpy (حرج · CVSS ~8.8):** مؤكدة بتقرير ASan وإثبات PoC؛ الأولوية: إصلاح فوري بإضافة فحص if (len > sizeof(buf)) return -1;.\n\n### ثانياً: الإنذارات الكاذبة المستبعدة\n1. **WebAPK exported=true:** طبيعي لربط التطبيق بالمتصفح عبر النوايا المخصصة ولا يشكل ثغرة منفردة.\n2. **SQL PreparedStatement:** الاستعلام مُعامل بالمتغيرات (Parameterized) وآمن ضد الحقن."},
    ]},
]

datasets_to_merge = [Dataset.from_list(CORE_CONVERSATIONS * 25)]

for extra_path in (Path("datasets/auto_curated.jsonl"), Path("datasets/self_play_train.jsonl")):
    if extra_path.exists():
        rows = []
        for line in extra_path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                obj = json.loads(line)
                if isinstance(obj.get("conversations"), list) and len(obj["conversations"]) >= 2:
                    rows.append({"conversations": obj["conversations"]})
            except json.JSONDecodeError:
                pass
        if rows:
            datasets_to_merge.append(Dataset.from_list(rows))
            print(f"Loaded {len(rows)} examples from {extra_path}.")

if os.environ.get("ZEROHUNTER_OFFLINE", "0") != "1":
    try:
        hf_vulns = load_dataset("CyberNative/Code_Vulnerability_Security_DPO", split="train[:1200]")
        mapped = []
        for row in hf_vulns:
            q_val = row.get("question")
            c_val = row.get("chosen")
            if isinstance(q_val, str) and isinstance(c_val, str) and q_val.strip() and c_val.strip():
                mapped.append({"conversations": [
                    {"role": "system", "content": "You are ZeroHunter. Identify vulnerabilities, explain clearly, and provide secure fixes."},
                    {"role": "user", "content": f"Audit this {row.get('lang', 'code')} snippet:\n{q_val}"},
                    {"role": "assistant", "content": c_val},
                ]})
        if mapped:
            datasets_to_merge.append(Dataset.from_list(mapped))
            print(f"Loaded {len(mapped)} vulnerability examples.")
    except Exception as exc:
        print("Skipping external vulnerability dataset fetch:", exc)

    try:
        hf_chat = load_dataset("mlabonne/FineTome-100k", split="train[:800]")
        chat_mapped = []
        for row in hf_chat:
            convs = row.get("conversations", [])
            norm = []
            for m in convs:
                val = m.get("value")
                frm = m.get("from", "")
                if not isinstance(val, str) or not val.strip():
                    continue
                role = "system" if frm == "system" else ("user" if frm in ("human", "user") else "assistant")
                norm.append({"role": role, "content": val})
            if len(norm) >= 2:
                chat_mapped.append({"conversations": norm})
        if chat_mapped:
            datasets_to_merge.append(Dataset.from_list(chat_mapped))
            print(f"Loaded {len(chat_mapped)} natural chat examples.")
    except Exception as exc:
        print("Skipping general chat dataset fetch:", exc)

dataset = concatenate_datasets(datasets_to_merge).shuffle(seed=3407)


def format_prompts(examples):
    texts = []
    for conv in examples["conversations"]:
        try:
            texts.append(tokenizer.apply_chat_template(conv, tokenize=False, add_generation_prompt=False))
        except Exception:
            texts.append("")
    return {"text": texts}


dataset = dataset.map(format_prompts, batched=True)
dataset = dataset.filter(lambda row: bool(row.get("text", "").strip()))

common_args = dict(
    per_device_train_batch_size=2,
    gradient_accumulation_steps=4,
    warmup_steps=10,
    num_train_epochs=2,
    learning_rate=2e-4,
    fp16=not is_bfloat16_supported(),
    bf16=is_bfloat16_supported(),
    logging_steps=10,
    optim="adamw_8bit",
    weight_decay=0.01,
    lr_scheduler_type="cosine",
    seed=3407,
    output_dir="outputs",
)

trainer_sig = inspect.signature(SFTTrainer.__init__).parameters
if SFTConfig is not None and "dataset_text_field" not in trainer_sig:
    cfg_kwargs = dict(common_args)
    sft_sig = inspect.signature(SFTConfig.__init__).parameters
    if "dataset_text_field" in sft_sig:
        cfg_kwargs["dataset_text_field"] = "text"
    if "max_seq_length" in sft_sig:
        cfg_kwargs["max_seq_length"] = MAX_SEQ_LENGTH
    if "max_length" in sft_sig:
        cfg_kwargs["max_length"] = MAX_SEQ_LENGTH
    training_args = SFTConfig(**cfg_kwargs)
else:
    training_args = TrainingArguments(**common_args)

trainer_kwargs = {
    "model": model,
    "train_dataset": dataset,
    "args": training_args,
}
if "processing_class" in trainer_sig:
    trainer_kwargs["processing_class"] = tokenizer
elif "tokenizer" in trainer_sig:
    trainer_kwargs["tokenizer"] = tokenizer
if "dataset_text_field" in trainer_sig:
    trainer_kwargs["dataset_text_field"] = "text"
if "max_seq_length" in trainer_sig:
    trainer_kwargs["max_seq_length"] = MAX_SEQ_LENGTH
if "dataset_num_proc" in trainer_sig:
    trainer_kwargs["dataset_num_proc"] = 2

trainer = SFTTrainer(**trainer_kwargs)

print("2. Starting training...")
trainer.train()

print(f"3. Exporting merged GGUF ({QUANT_METHOD}) to {OUTPUT_GGUF_DIR}...")
model.save_pretrained_gguf(OUTPUT_GGUF_DIR, tokenizer, quantization_method=QUANT_METHOD)
print("4. Done! Run upload_hf.py with HF_TOKEN set in your environment.")
