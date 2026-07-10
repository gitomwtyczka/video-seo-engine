import os
from cryptography.fernet import Fernet

def _get_fernet():
    key = os.getenv("FERNET_SECRET_KEY")
    if not key:
        raise RuntimeError("FERNET_SECRET_KEY not set")
    return Fernet(key.encode() if isinstance(key, str) else key)

def encrypt_token(plaintext):
    return _get_fernet().encrypt(plaintext.encode())

def decrypt_token(ciphertext):
    return _get_fernet().decrypt(ciphertext).decode()
