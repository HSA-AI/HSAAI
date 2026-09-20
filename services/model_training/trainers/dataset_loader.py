
from __future__ import annotations
from datasets import load_dataset

def load_training_dataset(dataset_path: str, max_seq_length: int):
    extension = dataset_path.split('.')[-1].lower()
    if extension == 'jsonl': extension = 'json'
    if extension in {'json','csv','text','txt'}:
        name = 'text' if extension == 'txt' else extension
        ds = load_dataset(name, data_files=dataset_path)
    else:
        ds = load_dataset(dataset_path)
    train = ds['train'] if 'train' in ds else next(iter(ds.values()))
    def normalize(example):
        if 'text' in example: text = example['text']
        elif 'prompt' in example and 'response' in example: text = f"### Instruction:\n{example['prompt']}\n\n### Response:\n{example['response']}"
        elif 'instruction' in example and 'output' in example: text = f"### Instruction:\n{example['instruction']}\n\n### Response:\n{example['output']}"
        else: text = '\n'.join(str(v) for v in example.values() if v is not None)
        return {'text': text[:max_seq_length * 8]}
    return train.map(normalize, remove_columns=train.column_names)
