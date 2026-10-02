"""Serviço unificado de recuperação de senha."""

import logging
import secrets
from uuid import UUID

from app.core.email import email_service
from app.core.redis import get_redis

logger = logging.getLogger(__name__)


class PasswordResetEmailError(Exception):
    """Exceção para falha no envio de e-mail de recuperação de senha."""

    def __init__(self, message: str = "Falha ao enviar e-mail de recuperação de senha"):
        super().__init__(message)
        self.message = message


async def execute_password_reset_request(
    user_id: UUID | str,
    email: str,
    nome: str,
    redis=None,
) -> str:
    """
    Helper unificado para solicitação de reset de senha.

    - Gera token URL-safe de 32 bytes
    - Armazena no Redis com TTL de 1 hora
    - Executa o envio de e-mail através do email_service
    - Se o envio falhar ou lançar exceção, invalida imediatamente o token no Redis
      e lança PasswordResetEmailError.
    """
    token = secrets.token_urlsafe(32)
    str_user_id = str(user_id)

    if redis is None:
        redis = await get_redis()
    await redis.store_password_reset_token(
        user_id=str_user_id,
        token=token,
        ttl_seconds=3600,
    )

    try:
        sent = await email_service.send_password_reset(
            email=email,
            token=token,
            nome=nome,
        )
        if not sent:
            logger.error(
                "Password reset email delivery failed",
                extra={"user_id": str_user_id},
            )
            await redis.invalidate_password_reset_token(token)
            raise PasswordResetEmailError("Falha ao enviar e-mail de recuperação de senha")
    except PasswordResetEmailError:
        raise
    except Exception as exc:
        logger.exception(
            "Password reset email provider unavailable for user %s: %s",
            str_user_id,
            exc,
        )
        await redis.invalidate_password_reset_token(token)
        raise PasswordResetEmailError(
            "Serviço de e-mail indisponível para recuperação de senha"
        ) from exc

    return token
