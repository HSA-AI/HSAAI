"""Real cryptographic operations, key continuity, tamper and config rejection."""
import base64
import concurrent.futures
from pathlib import Path
import pytest
from cryptography.fernet import Fernet
from backend_core.security import encryption as enc

@pytest.fixture(autouse=True)
def config(tmp_path,monkeypatch):
    monkeypatch.setattr(enc,'_ENABLE',True)
    monkeypatch.setattr(enc,'_RAW_KEY','a private test passphrase used only in test processes')
    monkeypatch.setattr(enc,'_SALT_PATH',str(tmp_path/'persistent'/'salt'))

@pytest.mark.parametrize('value',['English and العربية','a'*5000,'line 1\nline 2','🔒'])
def test_passphrase_roundtrip_and_random_ciphertext(value):
    first=enc.encrypt_text(value);second=enc.encrypt_text(value)
    assert first != second and value not in first
    assert enc.decrypt_text(first)==value and enc.decrypt_text(second)==value

def test_generated_fernet_key_is_used_as_encoded_key(monkeypatch):
    raw=Fernet.generate_key();monkeypatch.setattr(enc,'_RAW_KEY',raw.decode())
    token=enc.encrypt_text('secret')
    assert Fernet(raw).decrypt(token.encode())==b'secret'
    assert enc.decrypt_text(token)=='secret'

def test_salt_persists_and_has_private_mode():
    salt=enc._load_or_create_salt();assert len(salt)==16
    assert enc._load_or_create_salt()==salt
    assert Path(enc._SALT_PATH).stat().st_mode & 0o777==0o600

def test_concurrent_salt_initialization_returns_one_persisted_value():
    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
        salts=list(executor.map(lambda _:enc._load_or_create_salt(),range(24)))
    assert len(set(salts))==1 and len(salts[0])==16

@pytest.mark.parametrize('key',['','replace-with-your-secret','CHANGE_ME_NOW'])
def test_placeholder_keys_rejected(key,monkeypatch):
    monkeypatch.setattr(enc,'_RAW_KEY',key)
    with pytest.raises(RuntimeError):enc.encrypt_text('confidential')

def test_tampered_and_wrong_key_never_return_ciphertext(monkeypatch):
    monkeypatch.setattr(enc,'_RAW_KEY',Fernet.generate_key().decode())
    token=enc.encrypt_text('confidential');raw=bytearray(base64.urlsafe_b64decode(token));raw[-1]^=1
    with pytest.raises(ValueError,match='Decryption failed'):enc.decrypt_text(base64.urlsafe_b64encode(raw).decode())
    monkeypatch.setattr(enc,'_RAW_KEY',Fernet.generate_key().decode())
    with pytest.raises(ValueError,match='Decryption failed'):enc.decrypt_text(token)

@pytest.mark.parametrize('enabled,value',[(True,''),(False,''),(False,'plaintext')])
def test_explicit_disabled_or_empty_passthrough(enabled,value,monkeypatch):
    monkeypatch.setattr(enc,'_ENABLE',enabled)
    assert enc.encrypt_text(value)==value and enc.decrypt_text(value)==value

def test_corrupt_salt_fails_closed(tmp_path):
    path=Path(enc._SALT_PATH);path.parent.mkdir(parents=True);path.write_bytes(b'')
    with pytest.raises(RuntimeError,match='salt'):enc.encrypt_text('secret')
