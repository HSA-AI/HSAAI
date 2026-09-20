
from __future__ import annotations
from transformers import AutoModelForCausalLM, AutoTokenizer, TrainingArguments
from trl import SFTTrainer
from services.model_training.trainers.base_trainer import BaseEnterpriseTrainer, HFProgressCallback
from services.model_training.trainers.dataset_loader import load_training_dataset

class SFTEnterpriseTrainer(BaseEnterpriseTrainer):
    def run(self) -> dict:
        hp = self.config['hyperparameters']; base_model = self.config['base_model']; dataset_path = self.config['dataset_path']
        tokenizer = AutoTokenizer.from_pretrained(base_model, trust_remote_code=True)
        if tokenizer.pad_token is None: tokenizer.pad_token = tokenizer.eos_token
        model = AutoModelForCausalLM.from_pretrained(base_model, trust_remote_code=True, device_map='auto')
        dataset = load_training_dataset(dataset_path, hp['max_sequence_length'])
        args = TrainingArguments(output_dir=str(self.output_dir), num_train_epochs=hp['epochs'],
            per_device_train_batch_size=hp['batch_size'], gradient_accumulation_steps=hp['gradient_accumulation'],
            learning_rate=hp['learning_rate'], warmup_steps=hp['warmup_steps'], weight_decay=hp['weight_decay'],
            logging_steps=1, save_steps=100, save_total_limit=3, report_to=[], fp16=True)
        trainer = SFTTrainer(model=model, tokenizer=tokenizer, train_dataset=dataset, dataset_text_field='text',
            max_seq_length=hp['max_sequence_length'], args=args,
            callbacks=[HFProgressCallback(self.emit, self.ensure_not_cancelled)])
        trainer.train(resume_from_checkpoint=self.config.get('resume_from_checkpoint'))
        trainer.save_model(str(self.output_dir / 'model'))
        tokenizer.save_pretrained(str(self.output_dir / 'model'))
        result = {'artifact_path': str(self.output_dir / 'model'), 'method': 'SFT'}
        self.write_metadata(result); return result
