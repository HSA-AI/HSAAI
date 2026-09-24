import importlib
import json
import sys
import types
from types import SimpleNamespace

import pytest


def _module():
    return importlib.import_module("model_training.finetune_pipeline_v2")


def test_prepare_training_data_dedup_quality_and_split(tmp_path, monkeypatch):
    m = _module()

    # The target function imports these packages before branching by suffix.
    monkeypatch.setitem(sys.modules, "PyPDF2", types.ModuleType("PyPDF2"))
    monkeypatch.setitem(sys.modules, "docx", types.ModuleType("docx"))
    bs4 = types.ModuleType("bs4")
    bs4.BeautifulSoup = lambda text, parser: SimpleNamespace(get_text=lambda: text)
    monkeypatch.setitem(sys.modules, "bs4", bs4)

    raw = tmp_path / "raw"
    category = raw / "hr"
    category.mkdir(parents=True)
    (category / "source.txt").write_text("secret " + ("enterprise knowledge " * 20), encoding="utf-8")

    monkeypatch.setattr(m, "clean_text", lambda text: text.strip())
    monkeypatch.setattr(m, "redact_pii", lambda text: text.replace("secret", "[REDACTED]"))

    duplicate = {
        "instruction": "ما هي سياسة الإجازة السنوية في الشركة؟",
        "response": "سياسة الإجازة السنوية موثقة في دليل الموارد البشرية الداخلي.",
    }
    english = {
        "instruction": "Explain the enterprise leave policy in detail",
        "response": "The enterprise leave policy is documented in the internal HR handbook.",
    }
    bad = {"instruction": "bad", "response": "bad"}

    monkeypatch.setattr(
        m,
        "_generate_sft_pairs",
        lambda text, category, filename: [duplicate.copy(), duplicate.copy(), english.copy(), bad.copy()],
    )
    monkeypatch.setattr(m, "detect_language", lambda text: "ar" if any("\u0600" <= c <= "\u06ff" for c in text) else "en")
    monkeypatch.setattr(m, "quality_check", lambda ex: (ex["instruction"] != "bad", "ok" if ex["instruction"] != "bad" else "bad"))

    report = m.prepare_training_data(str(raw), str(tmp_path / "out"))

    assert report["stats"]["total_docs"] == 1
    assert report["stats"]["extracted"] == 1
    assert report["stats"]["pii_redacted"] == 1
    assert report["stats"]["deduplicated"] == 1
    assert report["stats"]["quality_passed"] == 2
    assert report["stats"]["quality_failed"] == 1
    assert report["stats"]["arabic"] == 1
    assert report["stats"]["english"] == 2  # english + the unique "bad" example before quality filtering
    assert report["train_examples"] + report["eval_examples"] == 2

    quality_report = json.loads((tmp_path / "out" / "data_quality_report.json").read_text(encoding="utf-8"))
    assert quality_report["stats"]["quality_passed"] == 2
    assert (tmp_path / "out" / "train.jsonl").exists()
    assert (tmp_path / "out" / "eval.jsonl").exists()


class _Tensor:
    def to(self, device):
        return self


class _Batch(dict):
    def __init__(self):
        super().__init__()
        self.input_ids = _Tensor()

    def to(self, device):
        return self


class _Tokenizer:
    pad_token = None
    eos_token = "<eos>"
    saved_to = None

    @classmethod
    def from_pretrained(cls, *args, **kwargs):
        return cls()

    def save_pretrained(self, output_dir):
        type(self).saved_to = output_dir

    def __call__(self, *args, **kwargs):
        return _Batch()

    def decode(self, *args, **kwargs):
        return "question expected answer"


class _Model:
    device = "cpu"
    gradient_enabled = False
    input_grads_enabled = False
    saved = False

    @classmethod
    def from_pretrained(cls, *args, **kwargs):
        return cls()

    def gradient_checkpointing_enable(self):
        self.gradient_enabled = True

    def enable_input_require_grads(self):
        self.input_grads_enabled = True

    def print_trainable_parameters(self):
        return None

    def generate(self, **kwargs):
        return [_Tensor()]

    def __call__(self, **kwargs):
        return SimpleNamespace(loss=1.0)


class _Dataset:
    def __init__(self, rows=None):
        self.rows = rows or [{"instruction": "q", "response": "a"}]
        self.column_names = ["instruction", "response"]

    def map(self, fn, remove_columns=None):
        self.rows = [fn(row) for row in self.rows]
        self.column_names = list(self.rows[0]) if self.rows else []
        return self

    def __len__(self):
        return len(self.rows)

    def __bool__(self):
        return bool(self.rows)


class _Trainer:
    last = None

    def __init__(self, **kwargs):
        self.kwargs = kwargs
        self.train_calls = []
        type(self).last = self

    def train(self, *args, **kwargs):
        self.train_calls.append((args, kwargs))

    def save_model(self, output_dir):
        self.saved_to = output_dir

    def evaluate(self):
        return {"eval_loss": 0.125}


class _NoGrad:
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def _install_training_fakes(monkeypatch, gpu_gb=24, cuda_available=True):
    torch = types.ModuleType("torch")

    class Cuda:
        @staticmethod
        def is_available():
            return cuda_available

        @staticmethod
        def get_device_name(index):
            return "Mock GPU"

        @staticmethod
        def get_device_properties(index):
            return SimpleNamespace(total_memory=gpu_gb * 1_000_000_000)

    torch.cuda = Cuda()
    torch.bfloat16 = "bf16"
    torch.float16 = "fp16"
    torch.no_grad = lambda: _NoGrad()
    torch.exp = lambda loss: SimpleNamespace(item=lambda: 2.5)
    monkeypatch.setitem(sys.modules, "torch", torch)

    transformers = types.ModuleType("transformers")
    transformers.AutoModelForCausalLM = _Model
    transformers.AutoTokenizer = _Tokenizer
    transformers.TrainingArguments = type("TrainingArguments", (), {})
    transformers.BitsAndBytesConfig = lambda **kwargs: SimpleNamespace(**kwargs)
    transformers.EarlyStoppingCallback = lambda **kwargs: SimpleNamespace(**kwargs)
    monkeypatch.setitem(sys.modules, "transformers", transformers)

    peft = types.ModuleType("peft")
    peft.LoraConfig = lambda **kwargs: SimpleNamespace(**kwargs)
    peft.get_peft_model = lambda model, config: model
    peft.prepare_model_for_kbit_training = lambda model: model
    monkeypatch.setitem(sys.modules, "peft", peft)

    trl = types.ModuleType("trl")
    trl.SFTTrainer = _Trainer
    trl.SFTConfig = lambda **kwargs: SimpleNamespace(**kwargs)
    monkeypatch.setitem(sys.modules, "trl", trl)

    datasets = types.ModuleType("datasets")
    datasets.load_dataset = lambda *args, **kwargs: _Dataset()
    monkeypatch.setitem(sys.modules, "datasets", datasets)


def test_lora_training_uses_mock_gpu_and_persists_metadata(tmp_path, monkeypatch):
    m = _module()
    _install_training_fakes(monkeypatch, gpu_gb=24)

    data = tmp_path / "data"
    out = tmp_path / "model"
    data.mkdir()
    out.mkdir()
    (data / "train.jsonl").write_text('{"instruction":"q","response":"a"}\n', encoding="utf-8")
    (data / "eval.jsonl").write_text('{"instruction":"q","response":"a"}\n', encoding="utf-8")

    metadata = m.run_lora_finetuning(
        "mock-model",
        str(data),
        str(out),
        batch_size=8,
        grad_accum=2,
        max_seq_length=4096,
        use_qlora=True,
        use_gradient_checkpointing=True,
        num_epochs=1,
    )

    assert metadata["gpu"] == "Mock GPU"
    assert metadata["precision"] == "fp16"
    assert metadata["batch_size"] == 1
    assert metadata["grad_accum"] >= 16
    assert metadata["max_seq_length"] <= 2048
    assert metadata["eval_examples"] == 1
    assert _Trainer.last.train_calls
    assert json.loads((out / "eval_results.json").read_text())["eval_loss"] == 0.125
    saved = json.loads((out / "training_metadata.json").read_text())
    assert saved["use_qlora"] is True


def test_lora_training_fails_cleanly_without_cuda(tmp_path, monkeypatch):
    m = _module()
    _install_training_fakes(monkeypatch, cuda_available=False)
    with pytest.raises(SystemExit) as exc:
        m.run_lora_finetuning("mock", str(tmp_path), str(tmp_path / "out"))
    assert exc.value.code == 1


def test_evaluate_model_with_mocked_torch_and_transformers(tmp_path, monkeypatch):
    m = _module()
    _install_training_fakes(monkeypatch, gpu_gb=80)

    eval_file = tmp_path / "eval.jsonl"
    eval_file.write_text(
        "\n".join([
            json.dumps({"instruction": "question", "response": "expected answer"}),
            json.dumps({"instruction": "question two", "response": "expected answer"}),
        ]) + "\n",
        encoding="utf-8",
    )
    model_dir = tmp_path / "model"
    model_dir.mkdir()

    report = m.evaluate_model(str(model_dir), str(eval_file))
    assert report["total_evaluated"] == 2
    assert report["accuracy"] == 1.0
    assert report["perplexity"] == 2.5
    assert json.loads((model_dir / "evaluation_report.json").read_text())["accuracy"] == 1.0
