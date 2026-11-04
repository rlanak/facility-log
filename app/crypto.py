"""Encryption at rest for the few secrets the database keeps: Discord
webhook URLs (they let anyone post in the channel), users' Discord tokens and
the capture API key (app_settings).

Not a vault: the key lives on the same machine. What it buys is that a copy
of facility_log.db alone (a backup, a file sent to someone, a leaked volume)
doesn't hand out those secrets.

Key, in this order:
- FACILITY_LOG_SECRET_KEY (env / .env) — recommended on the VPS, so the
  database volume and the key are kept apart;
- otherwise DATA_DIR/secret.key, created on first use (gitignored).
Values encrypted with either key keep decrypting (both are tried), so
setting the env key later doesn't lose anything; new writes use the env key.

Column type: EncryptedText. A value without the prefix is old plain text
from before this existed — it still reads, and is encrypted on the next
write (apply_migrations() re-saves them once).
"""

import base64
import hashlib
import os

from cryptography.fernet import Fernet, InvalidToken, MultiFernet
from sqlalchemy import Text
from sqlalchemy.types import TypeDecorator

PREFIX = "enc:v1:"

_fernet: MultiFernet | None = None


def _fernet_key(secret: str) -> bytes:
    # Any string works as FACILITY_LOG_SECRET_KEY; Fernet wants 32 urlsafe-b64 bytes.
    return base64.urlsafe_b64encode(hashlib.sha256(secret.encode()).digest())


def _get() -> MultiFernet:
    global _fernet
    if _fernet is None:
        from app.database import DATA_DIR

        keys = []
        env_key = os.environ.get("FACILITY_LOG_SECRET_KEY", "").strip()
        if env_key:
            keys.append(Fernet(_fernet_key(env_key)))
        key_file = DATA_DIR / "secret.key"
        if not key_file.exists() and not env_key:
            key_file.write_text(Fernet.generate_key().decode())
            try:
                os.chmod(key_file, 0o600)
            except OSError:
                pass
        if key_file.exists():
            keys.append(Fernet(key_file.read_text().strip().encode()))
        _fernet = MultiFernet(keys)
    return _fernet


def encrypt(value: str) -> str:
    if not value:
        return value
    return PREFIX + _get().encrypt(value.encode()).decode()


def decrypt(value: str) -> str:
    if not value or not value.startswith(PREFIX):
        return value
    try:
        return _get().decrypt(value[len(PREFIX) :].encode()).decode()
    except InvalidToken:
        # Key lost/changed: the secret is gone; behave as "not set" instead of crashing.
        return ""


class EncryptedText(TypeDecorator):
    impl = Text
    cache_ok = True

    def process_bind_param(self, value, dialect):
        return encrypt(value) if value is not None else None

    def process_result_value(self, value, dialect):
        return decrypt(value) if value is not None else None
