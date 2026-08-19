
from __future__ import annotations
import torch
from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig, TrainingArguments
from peft import LoraConfig, TaskType
from trl import SFTTrainer
from services.model_training.trainers.base_trainer import BaseEnterpriseTrainer, HFProgressCallback
from services.model_training.trainers.dataset_loader import load_training_dataset

class QLoraTrainer(BaseEnterpriseTrainer):
    def run(self) -> dict:
        hp = self.config['hyperparameters']; base_model = self.config['base_model']; dataset_path = self.config['dataset_path']
        tokenizer = AutoTokenizer.from_pretrained(base_model, trust_remote_code=True)
        if tokenizer.pad_token is None: tokenizer.pad_token = tokenizer.eos_token
        bnb = BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_quant_type='nf4', bnb_4bit_use_double_quant=True,
                                 bnb_4bit_compute_dtype=torch.bfloat16)
        model = AutoModelForCausalLM.from_pretrained(base_model, quantization_config=bnb, device_map='auto', trust_remote_code=True)
        dataset = load_training_dataset(dataset_path, hp['max_sequence_length'])
        peft_config = LoraConfig(task_type=TaskType.CAUSAL_LM, r=hp['lora_rank'], lora_alpha=hp['lora_alpha'],
                                 lora_dropout=hp['lora_dropout'], bias='none')
        args = TrainingArguments(output_dir=str(self.output_dir), num_train_epochs=hp['epochs'],
            per_device_train_batch_size=hp['batch_size'], gradient_accumulation_steps=hp['gradient_accumulation'],
            learning_rate=hp['learning_rate'], warmup_steps=hp['warmup_steps'], weight_decay=hp['weight_decay'],
            logging_steps=1, save_steps=100, save_total_limit=3, report_to=[], bf16=True)
        trainer = SFTTrainer(model=model, tokenizer=tokenizer, train_dataset=dataset, dataset_text_field='text',
            max_seq_length=hp['max_sequence_length'], peft_config=peft_config, args=args,
            callbacks=[HFProgressCallback(self.emit, self.ensure_not_cancelled)])
        trainer.train(resume_from_checkpoint=self.config.get('resume_from_checkpoint'))
        trainer.model.save_pretrained(str(self.output_dir / 'adapter'))
        tokenizer.save_pretrained(str(self.output_dir / 'adapter'))
        result = {'artifact_path': str(self.output_dir / 'adapter'), 'method': 'QLoRA'}
        self.write_metadata(result); return result
