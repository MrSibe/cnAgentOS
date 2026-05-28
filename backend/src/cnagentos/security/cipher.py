import base64

from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC


def _derive_key(password: str) -> bytes:
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=b"cnagentos-credential-v1",
        iterations=480000,
    )
    return base64.urlsafe_b64encode(kdf.derive(password.encode()))


_fernet: Fernet | None = None


def init_cipher(encryption_key: str) -> None:
    global _fernet
    key_bytes = _derive_key(encryption_key)
    _fernet = Fernet(key_bytes)


def encrypt(plaintext: str) -> str:
    if _fernet is None:
        raise RuntimeError("cipher not initialized, call init_cipher first")
    return _fernet.encrypt(plaintext.encode()).decode()


def decrypt(ciphertext: str) -> str:
    if _fernet is None:
        raise RuntimeError("cipher not initialized, call init_cipher first")
    return _fernet.decrypt(ciphertext.encode()).decode()


def generate_mask(api_key: str) -> str:
    if len(api_key) <= 8:
        return "********"
    return f"****{api_key[-4:]}"
