import os
from datasets import Dataset, concatenate_datasets, load_dataset
from trl import SFTTrainer
from transformers import TrainingArguments
from unsloth import FastLanguageModel, is_bfloat16_supported

MAX_SEQ_LENGTH = 4096
BASE_MODEL = "unsloth/Qwen2.5-Coder-3B-Instruct-bnb-4bit"
QUANT_METHOD = "q4_k_m"
OUTPUT_GGUF_DIR = os.environ.get("ZEROHUNTER_OUT_DIR", "./zerohunter_gguf")

# نسب المسارات الأربعة المعتمدة:
# 1) Memory/C++ (35%)  2) Web/APIs (30%)
# 3) Servers/Configs (20%)  4) Agent Tool-Calling & Arabic Status (15%)

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
    # Track 1: Memory Corruption + LibFuzzer Harness
    {"conversations": [
        {"role": "system", "content": "You are ZeroHunter, a C/C++ fuzzing harness specialist."},
        {"role": "user", "content": "Write ONLY valid C code implementing LLVMFuzzerTestOneInput for:\nint parse(const uint8_t *d, size_t s);"},
        {"role": "assistant", "content": "```c\n#include <stdint.h>\n#include <stddef.h>\nint parse(const uint8_t *d, size_t s);\nint LLVMFuzzerTestOneInput(const uint8_t *data, size_t size) {\n    parse(data, size);\n    return 0;\n}\n```"},
    ]},
    # Track 1b: ASan Crash Triage in Arabic
    {"conversations": [
        {"role": "system", "content": "You are ZeroHunter. Explain confirmed ASan crashes in Arabic and provide a safe patch."},
        {"role": "user", "content": "ASan Trace: ERROR: AddressSanitizer: stack-buffer-overflow on memcpy(e, d+2, len) where uint8_t e[32]."},
        {"role": "assistant", "content": "السبب الجذري: دالة memcpy تنسخ len بايت (قد يصل إلى 255) داخل مصفوفة ثابتة بحجم 32 بايت دون فحص الحد الأقصى.\nالإصلاح الآمن: أضف الشرط `if (len > sizeof(e)) return -1;` قبل النسخ."},
    ]},
    # Track 2: Web / Python / API Taint Analysis
    {"conversations": [
        {"role": "system", "content": "You are ZeroHunter. Analyze static findings in Arabic, filter false positives, and suggest fixes."},
        {"role": "user", "content": "Finding: subprocess.check_output(f'convert {user_fmt}', shell=True)"},
        {"role": "assistant", "content": "ثغرة مؤكدة (Command Injection): تمرير مدخلات المستخدم إلى shell=True يسمح بتنفيذ أوامر نظام.\nالإصلاح: مرّر قائمة معاملات `['convert', user_fmt]` واضبط `shell=False`."},
    ]},
    # Track 3: Server & Container Configuration Audit
    {"conversations": [
        {"role": "system", "content": "You are ZeroHunter. Audit server and container configurations for security flaws."},
        {"role": "user", "content": "nginx.conf: location /uploads/ { autoindex on; }"},
        {"role": "assistant", "content": "ملاحظة أمان (Directory Listing): تفعيل autoindex يكشف محتويات مجلد الرفع.\nالإصلاح: غيّر الإعداد إلى `autoindex off;` وأضف `server_tokens off;`."},
    ]},
    # Track 4: Live Interactive Progress & Arabic Chat
    {"conversations": [
        {"role": "system", "content": "You are ZeroHunter. Report live scan progress clearly in Arabic."},
        {"role": "user", "content": "State: phase=3/4 Fuzzing, progress=60%, eta=45s. Question: أين وصلت وكم باقي لك؟"},
        {"role": "assistant", "content": "أنا الآن في المرحلة 3/4 (تشغيل LibFuzzer مع AddressSanitizer)، نسبة الإنجاز 60%، والوقت المتبقي التقريبي 45 ثانية."},
    ]},
]

datasets_to_merge = [Dataset.from_list(CORE_CONVERSATIONS * 20)]

# دمج داتاسيت ثغرات مفتوحة المصدر من Hugging Face (اختياري حسب توفر الاتصال)
try:
    hf_vulns = load_dataset("CyberNative/Code_Vulnerability_Security_DPO", split="train[:1000]")
    mapped = []
    for row in hf_vulns:
        mapped.append({"conversations": [
            {"role": "system", "content": "You are ZeroHunter. Identify vulnerabilities and provide secure fixes."},
            {"role": "user", "content": f"Audit this {row.get('lang', 'code')} snippet:\n{row.get('question', '')}"},
            {"role": "assistant", "content": row.get("chosen", "")},
        ]})
    if mapped:
        datasets_to_merge.append(Dataset.from_list(mapped))
        print(f"Loaded {len(mapped)} real vulnerability examples from Hugging Face.")
except Exception as exc:
    print("Skipping external HF dataset fetch:", exc)

dataset = concatenate_datasets(datasets_to_merge).shuffle(seed=3407)


def format_prompts(examples):
    texts = [
        tokenizer.apply_chat_template(conv, tokenize=False, add_generation_prompt=False)
        for conv in examples["conversations"]
    ]
    return {"text": texts}


dataset = dataset.map(format_prompts, batched=True)

trainer = SFTTrainer(
    model=model,
    tokenizer=tokenizer,
    train_dataset=dataset,
    dataset_text_field="text",
    max_seq_length=MAX_SEQ_LENGTH,
    dataset_num_proc=2,
    args=TrainingArguments(
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
    ),
)

print("2. Starting training...")
trainer.train()

print(f"3. Exporting merged GGUF ({QUANT_METHOD}) to {OUTPUT_GGUF_DIR}...")
model.save_pretrained_gguf(OUTPUT_GGUF_DIR, tokenizer, quantization_method=QUANT_METHOD)
print("4. Done! Run upload_hf.py with HF_TOKEN set in your environment.")
