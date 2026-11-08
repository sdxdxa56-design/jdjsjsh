from unsloth import FastLanguageModel
import torch
from datasets import Dataset
from trl import SFTTrainer
from transformers import TrainingArguments
from unsloth import is_bfloat16_supported

max_seq_length = 2048
dtype = None
load_in_4bit = True

print("1. جاري تحميل النموذج...")
model, tokenizer = FastLanguageModel.from_pretrained(
    model_name = "unsloth/Qwen2.5-Coder-7B-Instruct-bnb-4bit",
    max_seq_length = max_seq_length,
    dtype = dtype,
    load_in_4bit = load_in_4bit,
)

model = FastLanguageModel.get_peft_model(
    model,
    r = 16,
    target_modules = ["q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"],
    lora_alpha = 16,
    lora_dropout = 0,
    bias = "none",
    use_gradient_checkpointing = "unsloth",
    random_state = 3407,
)

data = [
    {"conversations": [
        {"role": "user", "content": "Analyze this C code for vulnerabilities:\n\nvoid copy_data(char *input) {\n    char buffer[10];\n    strcpy(buffer, input);\n}"},
        {"role": "assistant", "content": "Vulnerability Found: Stack Buffer Overflow.\nRoot Cause: strcpy copies without checking length.\nFix: Use strncpy."}
    ]}
]

def format_prompts(examples):
    texts = []
    for conv in examples["conversations"]:
        text = tokenizer.apply_chat_template(conv, tokenize=False, add_generation_prompt=False)
        texts.append(text)
    return { "text" : texts }

dataset = Dataset.from_list(data)
dataset = dataset.map(format_prompts, batched=True)

trainer = SFTTrainer(
    model = model,
    tokenizer = tokenizer,
    train_dataset = dataset,
    dataset_text_field = "text",
    max_seq_length = max_seq_length,
    dataset_num_proc = 2,
    args = TrainingArguments(
        per_device_train_batch_size = 2,
        gradient_accumulation_steps = 4,
        warmup_steps = 5,
        max_steps = 30,
        learning_rate = 2e-4,
        fp16 = not is_bfloat16_supported(),
        bf16 = is_bfloat16_supported(),
        logging_steps = 1,
        optim = "adamw_8bit",
        weight_decay = 0.01,
        lr_scheduler_type = "linear",
        seed = 3407,
        output_dir = "outputs",
    ),
)

print("2. بدأ التدريب...")
trainer.train()
model.save_pretrained("zerohunter_model")
tokenizer.save_pretrained("zerohunter_model")
print("3. تم التدريب والحفظ بنجاح! النموذج جاهز.")
