from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

def test_internal_only_env_disables_external_ai():
    text = (ROOT / ".env.hsa-internal.example").read_text(encoding="utf-8")
    assert "ALLOW_EXTERNAL_AI=false" in text
    assert "Do not define OpenAI/Anthropic/Google/DeepSeek/Mistral/Cohere/Pinecone keys" in text
