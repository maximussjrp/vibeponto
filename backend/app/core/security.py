"""Utilitários de segurança: hashing, JWT, MFA."""

import base64
import hashlib
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID, uuid4

import bcrypt
from cryptography.fernet import Fernet, InvalidToken
from jose import JWTError, jwt
import pyotp

from app.core.config import settings


def hash_password(password: str) -> str:
    """Gera hash bcrypt da senha."""
    password_bytes = password.encode("utf-8")
    salt = bcrypt.gensalt(rounds=12)
    hashed = bcrypt.hashpw(password_bytes, salt)
    return hashed.decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verifica senha contra hash."""
    try:
        password_bytes = plain_password.encode("utf-8")
        hashed_bytes = hashed_password.encode("utf-8")
        return bcrypt.checkpw(password_bytes, hashed_bytes)
    except Exception:
        return False


def credential_fingerprint(password_hash: str) -> str:
    """SHA-256 hex do hash atual; versão opaca da credencial (USR-43).

    bcrypt usa salt aleatório, então toda troca de senha gera um fingerprint novo.
    Equivale em SQL a encode(sha256(convert_to(password_hash, 'UTF8')), 'hex').
    """
    return hashlib.sha256(password_hash.encode("utf-8")).hexdigest()


def create_access_token(
    data: dict[str, Any],
    expires_delta: timedelta | None = None,
) -> str:
    """Cria JWT access token."""
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (
        expires_delta or timedelta(minutes=settings.access_token_expire_minutes)
    )
    to_encode.update({"exp": expire, "type": "access", "jti": str(uuid4())})
    return jwt.encode(to_encode, settings.secret_key, algorithm=settings.jwt_algorithm)


def create_refresh_token(data: dict[str, Any]) -> str:
    """Cria JWT refresh token."""
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(days=settings.refresh_token_expire_days)
    to_encode.update({"exp": expire, "type": "refresh", "jti": str(uuid4())})
    return jwt.encode(to_encode, settings.secret_key, algorithm=settings.jwt_algorithm)


def decode_token(token: str) -> dict[str, Any] | None:
    """Decodifica e valida JWT."""
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[settings.jwt_algorithm],
                             options={"require_exp": True, "require_sub": True})
        UUID(payload["sub"])
        if payload.get("type") not in ("access", "refresh"):
            return None
        return payload
    except (JWTError, ValueError, TypeError, KeyError, AttributeError):
        return None


# MFA / TOTP
def generate_totp_secret() -> str:
    """Gera segredo TOTP para MFA."""
    return pyotp.random_base32()


def _mfa_fernet() -> Fernet:
    key = hashlib.sha256(settings.mfa_encryption_key.encode("utf-8")).digest()
    return Fernet(base64.urlsafe_b64encode(key))


def encrypt_totp_secret(secret: str) -> str:
    """Criptografa segredo TOTP em repouso com versao simples."""
    token = _mfa_fernet().encrypt(secret.encode("utf-8")).decode("ascii")
    return f"v1:{token}"


def decrypt_totp_secret(value: str) -> str:
    """Descriptografa segredo TOTP; aceita legado plaintext apenas em development."""
    if value.startswith("v1:"):
        try:
            return _mfa_fernet().decrypt(value[3:].encode("ascii")).decode("utf-8")
        except InvalidToken:
            raise ValueError("Invalid MFA secret") from None
    if settings.environment == "development":
        return value
    raise ValueError("Unsupported MFA secret format")


def get_totp_uri(secret: str, email: str) -> str:
    """Gera URI para QR Code do TOTP."""
    totp = pyotp.TOTP(secret)
    return totp.provisioning_uri(name=email, issuer_name=settings.app_name)


def verify_totp(secret: str, code: str) -> bool:
    """Verifica código TOTP."""
    totp = pyotp.TOTP(secret)
    return totp.verify(code, valid_window=1)
