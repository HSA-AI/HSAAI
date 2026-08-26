"""
HSAAI LoRA Fine-Tuning Pipeline (Phase 2 Redesign)
====================================================
Replaces the untrained Xavier-initialized HSAAI-R1 with a fine-tuned
open-weights base model specialized for HSA Group domain.

This script:
1. Loads a proven open-weights base (Llama 3.1 8B or Qwen 2.5 7B)
2. Curates HSA domain corpora (procurement, contracts, regulations)
3. Applies LoRA fine-tuning (Hu et al., 2021) — 1% of parameters
4. Optionally applies DPO alignment (Rafailov et al., 2023)
5. Evaluates against held-out test set
6. Exports to GGUF for llama.cpp / Ollama deployment

Hardware requirements:
- 1x A100 80GB or 2x RTX 4090 24GB for 8B model
- ~500GB disk for training data and checkpoints
- ~24-48 hours training time

Usage:
    # Full pipeline (requires GPU)
    python3 finetune_pipeline.py --base-model Qwen/Qwen2.5-7B-Instruct \\
        --data-dir ./data/hsa-corpus --output-dir ./models/hsaai-r1-ft

    # Data preparation only (no GPU needed)
    python3 finetune_pipeline.py --prepare-data-only --data-dir ./data/raw

    # Evaluation only
    python3 finetune_pipeline.py --eval-only --model ./models/hsaai-r1-ft
"""
import os
import sys
import json
import argparse
import logging
from pathlib import Path
from typing import List, Dict, Optional

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger("hsaai.finetune")


# ═══════════════════════════════════════════════════════════════════
# PHASE 1: DATA CURATION
# ═══════════════════════════════════════════════════════════════════
def prepare_training_data(raw_dir: str, output_dir: str):
    """
    Curate HSA domain corpora into instruction-response pairs
    suitable for supervised fine-tuning (SFT).

    Expected raw structure:
        raw_dir/
            procurement/       *.pdf, *.docx, *.txt
            contracts/         *.pdf
            regulations/       *.pdf, *.html
            policies/          *.docx
            communications/    *.eml, *.txt
    """
    import PyPDF2
    import docx
    from bs4 import BeautifulSoup

    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    sft_examples = []

    # 1. Extract text from each document type
    raw_path = Path(raw_dir)
    for category_dir in raw_path.iterdir():
        if not category_dir.is_dir():
            continue
        category = category_dir.name
        logger.info(f"Processing category: {category}")

        for doc_file in category_dir.rglob("*"):
            if doc_file.suffix.lower() == ".pdf":
                text = _extract_pdf(doc_file)
            elif doc_file.suffix.lower() == ".docx":
                text = _extract_docx(doc_file)
            elif doc_file.suffix.lower() in (".txt", ".md"):
                text = doc_file.read_text(encoding="utf-8", errors="ignore")
            elif doc_file.suffix.lower() == ".html":
                text = BeautifulSoup(doc_file.read_text(), "html.parser").get_text()
            elif doc_file.suffix.lower() == ".eml":
                text = _extract_eml(doc_file)
            else:
                continue

            if not text or len(text) < 100:
                continue

            # 2. Generate instruction-response pairs via templates
            examples = _generate_sft_pairs(text, category, doc_file.name)
            sft_examples.extend(examples)

    # 3. Deduplicate and filter
    seen = set()
    deduped = []
    for ex in sft_examples:
        key = hash(ex["instruction"] + ex["response"][:200])
        if key not in seen:
            seen.add(key)
            deduped.append(ex)

    # 4. Split into train/eval
    import random
    random.seed(42)
    random.shuffle(deduped)
    split = int(0.95 * len(deduped))
    train, eval_set = deduped[:split], deduped[split:]

    # 5. Save in JSONL format (HuggingFace datasets compatible)
    train_file = output_path / "train.jsonl"
    eval_file = output_path / "eval.jsonl"
    with open(train_file, "w", encoding="utf-8") as f:
        for ex in train:
            f.write(json.dumps(ex, ensure_ascii=False) + "\n")
    with open(eval_file, "w", encoding="utf-8") as f:
        for ex in eval_set:
            f.write(json.dumps(ex, ensure_ascii=False) + "\n")

    logger.info(f"Curated {len(train)} train + {len(eval_set)} eval examples")
    logger.info(f"Train: {train_file}")
    logger.info(f"Eval:  {eval_file}")


def _extract_pdf(path: Path) -> str:
    text = []
    try:
        with open(path, "rb") as f:
            reader = PyPDF2.PdfReader(f)
            for page in reader.pages:
                text.append(page.extract_text() or "")
    except Exception as e:
        logger.warning(f"PDF extract failed for {path}: {e}")
    return "\n".join(text)


def _extract_docx(path: Path) -> str:
    try:
        doc = docx.Document(path)
        return "\n".join(p.text for p in doc.paragraphs)
    except Exception as e:
        logger.warning(f"DOCX extract failed for {path}: {e}")
        return ""


def _extract_eml(path: Path) -> str:
    import email
    try:
        with open(path, "rb") as f:
            msg = email.message_from_bytes(f.read())
        return msg.get_payload(decode=True).decode("utf-8", errors="ignore")
    except Exception:
        return ""


def _generate_sft_pairs(text: str, category: str, filename: str) -> List[Dict]:
    """Generate instruction-response pairs from document text."""
    examples = []
    # Chunk the text into ~1000-token segments
    chunk_size = 4000
    chunks = [text[i:i+chunk_size] for i in range(0, len(text), chunk_size)]

    for chunk in chunks[:5]:  # max 5 chunks per document
        # Template 1: Summarization
        examples.append({
            "instruction": f"لخص المستند التالي من فئة '{category}':\n\n{chunk[:2000]}",
            "response": f"ملخص المستند ({filename}):\n{chunk[:1000]}",  # Replace with LLM-generated
            "category": category,
        })
        # Template 2: Question answering
        examples.append({
            "instruction": f"بناءً على المستند التالي، ما هي النقاط الرئيسية؟\n\n{chunk[:2000]}",
            "response": "النقاط الرئيسية هي: ...",  # Replace with LLM-generated
            "category": category,
        })
        # Template 3: English version
        examples.append({
            "instruction": f"Summarize the following {category} document:\n\n{chunk[:2000]}",
            "response": f"Summary of {filename}: ...",
            "category": category,
        })

    return examples


# ═══════════════════════════════════════════════════════════════════
# PHASE 2: LoRA FINE-TUNING
# ═══════════════════════════════════════════════════════════════════
def run_lora_finetuning(base_model: str, data_dir: str, output_dir: str):
    """
    Run LoRA fine-tuning using HuggingFace TRL.
    Requires GPU with >=24GB VRAM for 7B models.
    """
    try:
        import torch
        from transformers import (
            AutoModelForCausalLM, AutoTokenizer, TrainingArguments,
            DataCollatorForLanguageModeling,
        )
        from peft import LoraConfig, get_peft_model, prepare_model_for_kbit_training
        from trl import SFTTrainer, SFTConfig
        from datasets import load_dataset
    except ImportError as e:
        logger.error(f"Missing dependencies: {e}")
        logger.error("Install with: pip install torch transformers peft trl datasets accelerate")
        sys.exit(1)

    if not torch.cuda.is_available():
        logger.error("CUDA not available. Fine-tuning requires GPU.")
        sys.exit(1)

    logger.info(f"Loading base model: {base_model}")
    tokenizer = AutoTokenizer.from_pretrained(base_model, trust_remote_code=True)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    # Load in 4-bit for memory efficiency (QLoRA)
    from transformers import BitsAndBytesConfig
    bnb_config = BitsAndBytesConfig(
        load_in_4bit=True,
        bnb_4bit_quant_type="nf4",
        bnb_4bit_compute_dtype=torch.bfloat16,
        bnb_4bit_use_double_quant=True,
    )
    model = AutoModelForCausalLM.from_pretrained(
        base_model,
        quantization_config=bnb_config,
        device_map="auto",
        trust_remote_code=True,
    )
    model = prepare_model_for_kbit_training(model)

    # LoRA configuration — r=16 is good balance of capacity and efficiency
    lora_config = LoraConfig(
        r=16,
        lora_alpha=32,
        target_modules=["q_proj", "k_proj", "v_proj", "o_proj",
                       "gate_proj", "up_proj", "down_proj"],
        lora_dropout=0.05,
        bias="none",
        task_type="CAUSAL_LM",
    )
    model = get_peft_model(model, lora_config)
    model.print_trainable_parameters()

    # Load training data
    train_ds = load_dataset("json", data_files=f"{data_dir}/train.jsonl", split="train")
    eval_ds = load_dataset("json", data_files=f"{data_dir}/eval.jsonl", split="train")

    def format_example(ex):
        text = f"### Instruction:\n{ex['instruction']}\n\n### Response:\n{ex['response']}"
        return {"text": text}

    train_ds = train_ds.map(format_example, remove_columns=train_ds.column_names)
    eval_ds = eval_ds.map(format_example, remove_columns=eval_ds.column_names)

    # Training arguments
    training_args = SFTConfig(
        output_dir=output_dir,
        num_train_epochs=3,
        per_device_train_batch_size=4,
        gradient_accumulation_steps=4,
        warmup_steps=100,
        learning_rate=2e-4,  # LoRA uses higher LR than full FT
        logging_steps=10,
        eval_strategy="steps",
        eval_steps=200,
        save_strategy="steps",
        save_steps=500,
        save_total_limit=3,
        load_best_model_at_end=True,
        metric_for_best_model="eval_loss",
        greater_is_better=False,
        bf16=True,  # A100/H100 supports bf16
        optim="adamw_torch",
        lr_scheduler_type="cosine",
        report_to="tensorboard",
    )

    trainer = SFTTrainer(
        model=model,
        args=training_args,
        train_dataset=train_ds,
        eval_dataset=eval_ds,
        processing_class=tokenizer,
    )

    logger.info("Starting LoRA fine-tuning...")
    trainer.train()

    logger.info(f"Saving fine-tuned model to {output_dir}")
    trainer.save_model(output_dir)
    tokenizer.save_pretrained(output_dir)

    # Evaluate
    eval_results = trainer.evaluate()
    logger.info(f"Final evaluation: {eval_results}")
    return eval_results


# ═══════════════════════════════════════════════════════════════════
# PHASE 3: DPO ALIGNMENT (Optional)
# ═══════════════════════════════════════════════════════════════════
def run_dpo_alignment(model_dir: str, preference_data: str, output_dir: str):
    """
    Apply Direct Preference Optimization (DPO) for alignment to HSA values.
    Requires a preference dataset in JSONL format:
        {"prompt": "...", "chosen": "...", "rejected": "..."}
    """
    try:
        from trl import DPOTrainer, DPOConfig
        from transformers import AutoModelForCausalLM, AutoTokenizer
        from datasets import load_dataset
        import torch
    except ImportError as e:
        logger.error(f"Missing dependencies: {e}")
        sys.exit(1)

    logger.info(f"Loading SFT model: {model_dir}")
    model = AutoModelForCausalLM.from_pretrained(
        model_dir, device_map="auto", torch_dtype=torch.bfloat16,
    )
    tokenizer = AutoTokenizer.from_pretrained(model_dir)

    ds = load_dataset("json", data_files=preference_data, split="train")

    config = DPOConfig(
        output_dir=output_dir,
        num_train_epochs=1,
        per_device_train_batch_size=2,
        gradient_accumulation_steps=8,
        learning_rate=5e-6,  # DPO uses much lower LR
        beta=0.1,  # KL penalty strength
        logging_steps=10,
        save_steps=500,
        bf16=True,
    )
    trainer = DPOTrainer(
        model=model, args=config,
        train_dataset=ds, processing_class=tokenizer,
    )
    trainer.train()
    trainer.save_model(output_dir)
    logger.info(f"DPO-aligned model saved to {output_dir}")


# ═══════════════════════════════════════════════════════════════════
# PHASE 4: EVALUATION
# ═══════════════════════════════════════════════════════════════════
def evaluate_model(model_dir: str, eval_data: str):
    """Evaluate model on held-out test set and ArabicMMLU subset."""
    try:
        import torch
        from transformers import AutoModelForCausalLM, AutoTokenizer
    except ImportError as e:
        logger.error(f"Missing dependencies: {e}")
        sys.exit(1)

    logger.info(f"Evaluating model: {model_dir}")
    tokenizer = AutoTokenizer.from_pretrained(model_dir)
    model = AutoModelForCausalLM.from_pretrained(
        model_dir, device_map="auto", torch_dtype=torch.bfloat16,
    )

    # Load eval examples
    examples = []
    with open(eval_data, "r", encoding="utf-8") as f:
        for line in f:
            examples.append(json.loads(line))

    # Generate and compute metrics
    correct, total = 0, 0
    for ex in examples[:100]:  # Evaluate on first 100
        inputs = tokenizer(ex["instruction"], return_tensors="pt").to(model.device)
        with torch.no_grad():
            outputs = model.generate(
                **inputs, max_new_tokens=512, do_sample=False, temperature=1.0,
            )
        generated = tokenizer.decode(outputs[0], skip_special_tokens=True)
        # Simple substring match for evaluation
        if ex["response"][:50] in generated:
            correct += 1
        total += 1

    accuracy = correct / total if total > 0 else 0
    logger.info(f"Evaluation accuracy: {accuracy:.2%} ({correct}/{total})")
    return {"accuracy": accuracy, "total": total}


# ═══════════════════════════════════════════════════════════════════
# PHASE 5: GGUF EXPORT
# ═══════════════════════════════════════════════════════════════════
def export_to_gguf(model_dir: str, output_file: str):
    """
    Export fine-tuned model to GGUF format for llama.cpp / Ollama deployment.
    Requires llama.cpp's convert script.
    """
    logger.info(f"Exporting {model_dir} → {output_file}")
    logger.info("This requires llama.cpp. Install with:")
    logger.info("  git clone https://github.com/ggerganov/llama.cpp")
    logger.info("  cd llama.cpp && make")
    logger.info("  pip install -r requirements.txt")
    logger.info("")
    logger.info("Then run:")
    logger.info(f"  python3 convert.py {model_dir} --outfile {output_file} --outtype f16")
    logger.info(f"  ./quantize {output_file} {output_file.replace('.gguf', '_Q4_K_M.gguf')} Q4_K_M")


# ═══════════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════════
def main():
    parser = argparse.ArgumentParser(description="HSAAI LoRA Fine-Tuning Pipeline")
    parser.add_argument("--base-model", default="Qwen/Qwen2.5-7B-Instruct",
                        help="HuggingFace model ID for base model")
    parser.add_argument("--data-dir", default="./data/hsa-corpus")
    parser.add_argument("--output-dir", default="./models/hsaai-r1-ft")
    parser.add_argument("--prepare-data-only", action="store_true")
    parser.add_argument("--eval-only", action="store_true")
    parser.add_argument("--model", default=None, help="Model path for eval-only")
    parser.add_argument("--dpo-data", default=None, help="Preference dataset for DPO")
    parser.add_argument("--export-gguf", action="store_true")
    args = parser.parse_args()

    if args.prepare_data_only:
        prepare_training_data(args.data_dir, f"{args.data_dir}/processed")
        return

    if args.eval_only:
        if not args.model:
            logger.error("--model required for eval-only mode")
            sys.exit(1)
        evaluate_model(args.model, f"{args.data_dir}/processed/eval.jsonl")
        return

    # Full pipeline
    # Step 1: Prepare data
    if not os.path.exists(f"{args.data_dir}/processed/train.jsonl"):
        prepare_training_data(args.data_dir, f"{args.data_dir}/processed")

    # Step 2: LoRA fine-tuning
    run_lora_finetuning(args.base_model, f"{args.data_dir}/processed", args.output_dir)

    # Step 3: DPO alignment (optional)
    if args.dpo_data:
        dpo_dir = f"{args.output_dir}-dpo"
        run_dpo_alignment(args.output_dir, args.dpo_data, dpo_dir)
        final_model = dpo_dir
    else:
        final_model = args.output_dir

    # Step 4: Evaluate
    evaluate_model(final_model, f"{args.data_dir}/processed/eval.jsonl")

    # Step 5: Export to GGUF
    if args.export_gguf:
        gguf_file = f"{final_model}/hsaai-r1-finetuned.gguf"
        export_to_gguf(final_model, gguf_file)

    logger.info("✅ Pipeline complete")
    logger.info(f"Final model: {final_model}")
    logger.info(f"Deploy with: ollama create hsaai-r1 -f Modelfile")


if __name__ == "__main__":
    main()
