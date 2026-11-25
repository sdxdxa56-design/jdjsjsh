import argparse
import json
from pathlib import Path
from typing import List

from .registry import (
    BASE_MODEL_ID,
    LORA_ALPHA,
    LORA_RANK,
    LORA_TARGET_MODULES,
    SWARM_AGENTS,
    build_swarm10_datasets,
)


def train_single_adapter(
    agent: dict,
    dataset_path: Path,
    output_dir: Path,
    epochs: int = 3,
    rank: int = LORA_RANK,
) -> dict:
    import torch
    from datasets import Dataset
    from peft import LoraConfig, TaskType, get_peft_model
    from transformers import (
        AutoModelForCausalLM,
        AutoTokenizer,
        DataCollatorForLanguageModeling,
        Trainer,
        TrainingArguments,
    )

    records: List[dict] = []
    for line in dataset_path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            records.append(json.loads(line))

    tokenizer = AutoTokenizer.from_pretrained(BASE_MODEL_ID, trust_remote_code=False)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    texts: List[str] = []
    for rec in records:
        msgs = rec["messages"]
        rendered = "\n".join(f"<|{m['role']}|>\n{m['content']}" for m in msgs) + "\n<|endoftext|>"
        texts.append(rendered)

    ds = Dataset.from_dict({"text": texts})

    def tokenize_fn(batch):
        return tokenizer(batch["text"], truncation=True, max_length=512, padding="max_length")

    tokenized = ds.map(tokenize_fn, batched=True, remove_columns=["text"])

    dtype = torch.float16 if torch.cuda.is_available() else torch.float32
    base_model = AutoModelForCausalLM.from_pretrained(BASE_MODEL_ID, torch_dtype=dtype)

    lora_cfg = LoraConfig(
        task_type=TaskType.CAUSAL_LM,
        r=rank,
        lora_alpha=LORA_ALPHA,
        lora_dropout=0.05,
        target_modules=LORA_TARGET_MODULES,
    )
    peft_model = get_peft_model(base_model, lora_cfg)

    adapter_dir = output_dir / agent["folder"]
    adapter_dir.mkdir(parents=True, exist_ok=True)
    tmp_ckpt = output_dir / f".tmp_{agent['id']}"

    args = TrainingArguments(
        output_dir=str(tmp_ckpt),
        num_train_epochs=epochs,
        per_device_train_batch_size=1,
        gradient_accumulation_steps=2,
        learning_rate=2e-4,
        logging_steps=1,
        save_strategy="no",
        fp16=torch.cuda.is_available(),
        report_to="none",
    )

    trainer = Trainer(
        model=peft_model,
        args=args,
        train_dataset=tokenized,
        data_collator=DataCollatorForLanguageModeling(tokenizer=tokenizer, mlm=False),
    )
    trainer.train()
    peft_model.save_pretrained(str(adapter_dir))
    tokenizer.save_pretrained(str(adapter_dir))

    meta = {
        "agent_id": agent["id"],
        "role": agent["arabic_role"],
        "base_model": BASE_MODEL_ID,
        "lora_rank": rank,
        "samples": len(records),
    }
    (adapter_dir / "swarm_agent_meta.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return meta


def main() -> None:
    parser = argparse.ArgumentParser(description="Train all 10 specialized LoRA adapters on Colab GPU")
    parser.add_argument("--epochs", type=int, default=3)
    parser.add_argument("--rank", type=int, default=LORA_RANK)
    parser.add_argument("--output-dir", type=str, default="lora_adapters")
    parser.add_argument("--agent", type=str, default="all")
    args = parser.parse_args()

    build_swarm10_datasets()
    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    summary = []
    for agent in SWARM_AGENTS:
        if args.agent != "all" and args.agent != agent["id"]:
            continue
        ds_path = Path("datasets/swarm10") / f"{agent['id']}_train.jsonl"
        meta = train_single_adapter(agent, ds_path, out_dir, epochs=args.epochs, rank=args.rank)
        summary.append(meta)
        print(json.dumps({"trained": meta}, ensure_ascii=False), flush=True)

    (out_dir / "manifest.json").write_text(
        json.dumps({"base_model": BASE_MODEL_ID, "adapters": summary}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
