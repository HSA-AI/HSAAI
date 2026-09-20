from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path

logger = logging.getLogger("hsaai.local_trainer")


def require_optional_training_dependencies():
    missing = []
    for module in ["torch", "transformers", "datasets", "peft"]:
        try:
            __import__(module)
        except Exception:
            missing.append(module)
    if missing:
        raise RuntimeError(
            "Missing optional training dependencies: " + ", ".join(missing) +
            ". Install requirements-training.txt on a GPU-enabled environment."
        )


def main() -> None:
    parser = argparse.ArgumentParser(description="HSAAI local LoRA/QLoRA trainer")
    parser.add_argument("--job-id", required=True)
    parser.add_argument("--base-model", required=True)
    parser.add_argument("--dataset", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--method", choices=["lora", "qlora"], default="lora")
    parser.add_argument("--epochs", type=int, default=3)
    parser.add_argument("--batch-size", type=int, default=4)
    parser.add_argument("--learning-rate", type=float, default=2e-4)
    parser.add_argument("--max-seq-length", type=int, default=2048)
    args = parser.parse_args()

    logger.info(f"[HSAAI TRAINER] job={args.job_id} method={args.method}")
    logger.info(f"[HSAAI TRAINER] base_model={args.base_model}")
    logger.info(f"[HSAAI TRAINER] dataset={args.dataset}")

    require_optional_training_dependencies()

    import torch
    from datasets import load_dataset
    from transformers import AutoModelForCausalLM, AutoTokenizer, TrainingArguments, Trainer, DataCollatorForLanguageModeling
    from peft import LoraConfig, get_peft_model, prepare_model_for_kbit_training

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    tokenizer = AutoTokenizer.from_pretrained(args.base_model, trust_remote_code=True, local_files_only=True)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    load_kwargs = {"trust_remote_code": True, "local_files_only": True, "device_map": "auto"}
    if args.method == "qlora":
        load_kwargs.update({"load_in_4bit": True})

    model = AutoModelForCausalLM.from_pretrained(args.base_model, **load_kwargs)
    if args.method == "qlora":
        model = prepare_model_for_kbit_training(model)

    lora_config = LoraConfig(
        r=16,
        lora_alpha=32,
        lora_dropout=0.05,
        bias="none",
        task_type="CAUSAL_LM",
        target_modules=["q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"],
    )
    model = get_peft_model(model, lora_config)

    data_files = args.dataset
    dataset = load_dataset("json", data_files=data_files, split="train")

    def tokenize(example):
        text = example.get("text") or example.get("prompt", "") + "\n" + example.get("response", "")
        return tokenizer(text, truncation=True, max_length=args.max_seq_length)

    tokenized = dataset.map(tokenize, remove_columns=dataset.column_names)

    training_args = TrainingArguments(
        output_dir=str(output_dir),
        num_train_epochs=args.epochs,
        per_device_train_batch_size=args.batch_size,
        learning_rate=args.learning_rate,
        logging_steps=5,
        save_steps=100,
        save_total_limit=2,
        bf16=torch.cuda.is_available(),
        report_to=[],
    )

    trainer = Trainer(
        model=model,
        args=training_args,
        train_dataset=tokenized,
        data_collator=DataCollatorForLanguageModeling(tokenizer=tokenizer, mlm=False),
    )
    trainer.train()
    model.save_pretrained(output_dir)
    tokenizer.save_pretrained(output_dir)
    (output_dir / "hsaai_training_manifest.json").write_text(json.dumps(vars(args), indent=2), encoding="utf-8")
    logger.info(f"[HSAAI TRAINER] completed output={output_dir}")


if __name__ == "__main__":
    main()
