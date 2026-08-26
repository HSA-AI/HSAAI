
from __future__ import annotations
from transformers import AutoModelForCausalLM, AutoTokenizer, TrainingArguments, Trainer, DataCollatorForLanguageModeling
from peft import LoraConfig, get_peft_model, TaskType
from services.model_training.trainers.base_trainer import BaseEnterpriseTrainer, HFProgressCallback
from services.model_training.trainers.dataset_loader import load_training_dataset

class LoraTrainer(BaseEnterpriseTrainer):
    def run(self) -> dict:
        hp = self.config['hyperparameters']; base_model = self.config['base_model']; dataset_path = self.config['dataset_path']
        tokenizer = AutoTokenizer.from_pretrained(base_model, trust_remote_code=True)
        if tokenizer.pad_token is None: tokenizer.pad_token = tokenizer.eos_token
        dataset = load_training_dataset(dataset_path, hp['max_sequence_length'])
        def tokenize(batch):
            return tokenizer(batch['text'], truncation=True, padding=False, max_length=hp['max_sequence_length'])
        tokenized = dataset.map(tokenize, batched=True, remove_columns=['text'])
        model = AutoModelForCausalLM.from_pretrained(base_model, trust_remote_code=True, device_map='auto')
        # FIX v2.0: Explicitly target all 7 attention + MLP projection layers
        lora_target_modules = hp.get(
            'lora_target_modules',
            ["q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"],
        )
        peft_config = LoraConfig(
            task_type=TaskType.CAUSAL_LM,
            r=hp['lora_rank'],
            lora_alpha=hp['lora_alpha'],
            lora_dropout=hp['lora_dropout'],
            bias='none',
            target_modules=lora_target_modules,
        )
        model = get_peft_model(model, peft_config)
        args = TrainingArguments(output_dir=str(self.output_dir), num_train_epochs=hp['epochs'],
            per_device_train_batch_size=hp['batch_size'], gradient_accumulation_steps=hp['gradient_accumulation'],
            learning_rate=hp['learning_rate'], warmup_steps=hp['warmup_steps'], weight_decay=hp['weight_decay'],
            logging_steps=1, save_steps=100, save_total_limit=3, report_to=[], fp16=True)
        trainer = Trainer(model=model, args=args, train_dataset=tokenized,
            data_collator=DataCollatorForLanguageModeling(tokenizer=tokenizer, mlm=False),
            callbacks=[HFProgressCallback(self.emit, self.ensure_not_cancelled)])
        trainer.train(resume_from_checkpoint=self.config.get('resume_from_checkpoint'))
        model.save_pretrained(str(self.output_dir / 'adapter'))
        tokenizer.save_pretrained(str(self.output_dir / 'adapter'))
        result = {'artifact_path': str(self.output_dir / 'adapter'), 'method': 'LoRA'}
        self.write_metadata(result); return result
