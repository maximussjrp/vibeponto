"""MFA helpers: encrypted TOTP, backup codes and throttling."""

import secrets
from datetime import UTC, datetime
from uuid import UUID

import pyotp
from fastapi import HTTPException, Request
from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.redis import get_redis
from app.core.security import decrypt_totp_secret, hash_password, verify_password
from app.models import MFABackupCode, Usuario


def generate_backup_codes(count: int | None = None) -> list[str]:
    total = count or settings.mfa_backup_codes_count
    return [secrets.token_urlsafe(9).replace("-", "").replace("_", "")[:12].upper() for _ in range(total)]


async def replace_backup_codes(db: AsyncSession, usuario_id: UUID, codes: list[str]) -> None:
    await db.execute(delete(MFABackupCode).where(MFABackupCode.usuario_id == usuario_id))
    for code in codes:
        db.add(MFABackupCode(usuario_id=usuario_id, code_hash=hash_password(code)))


async def check_mfa_rate_limit(usuario_id: UUID, request: Request | None = None) -> None:
    redis = await get_redis()
    ip = request.client.host if request and request.client else "unknown"
    allowed, _, reset_at = await redis.check_rate_limit(
        f"mfa:{usuario_id}:{ip}",
        settings.mfa_attempts_limit,
        settings.mfa_attempts_window_seconds,
    )
    if not allowed:
        raise HTTPException(
            status_code=429,
            detail="Muitas tentativas de MFA. Tente novamente em instantes.",
            headers={"Retry-After": str(max(1, reset_at - int(datetime.now(UTC).timestamp())))},
        )


def _matching_totp_step(secret: str, code: str, now: datetime | None = None) -> int | None:
    totp = pyotp.TOTP(secret)
    now = now or datetime.now(UTC)
    for offset in (-1, 0, 1):
        candidate = now.timestamp() + offset * int(totp.interval)
        if totp.verify(code, for_time=candidate, valid_window=0):
            return int(candidate // int(totp.interval))
    return None


async def verify_totp_for_user(db: AsyncSession, usuario: Usuario, code: str) -> bool:
    if not usuario.mfa_secret:
        return False
    try:
        secret = decrypt_totp_secret(usuario.mfa_secret)
    except ValueError:
        return False

    step = _matching_totp_step(secret, code)
    if step is None:
        return False
    if usuario.mfa_last_totp_step is not None and step <= usuario.mfa_last_totp_step:
        return False

    await db.execute(
        update(Usuario)
        .where(Usuario.id == usuario.id)
        .values(mfa_last_totp_step=step)
    )
    usuario.mfa_last_totp_step = step
    return True


async def consume_backup_code(db: AsyncSession, usuario_id: UUID, code: str) -> bool:
    result = await db.execute(
        select(MFABackupCode)
        .where(MFABackupCode.usuario_id == usuario_id, MFABackupCode.used_at.is_(None))
        .with_for_update()
    )
    for backup_code in result.scalars().all():
        if verify_password(code, backup_code.code_hash):
            backup_code.used_at = datetime.now(UTC)
            return True
    return False


async def verify_mfa_code(
    db: AsyncSession,
    usuario: Usuario,
    code: str,
    request: Request | None = None,
    allow_backup: bool = True,
) -> bool:
    await check_mfa_rate_limit(usuario.id, request)
    normalized = code.strip().replace(" ", "").replace("-", "")
    if len(normalized) == 6 and normalized.isdigit():
        return await verify_totp_for_user(db, usuario, normalized)
    if allow_backup:
        return await consume_backup_code(db, usuario.id, normalized.upper())
    return False
