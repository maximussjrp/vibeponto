"""Serviço de email com suporte a múltiplos providers."""

import asyncio
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass

import aiohttp

from app.core.config import settings

logger = logging.getLogger(__name__)


@dataclass
class EmailMessage:
    """Representa uma mensagem de email."""

    to: str | list[str]
    subject: str
    html: str
    text: str | None = None
    from_email: str | None = None
    from_name: str | None = None
    reply_to: str | None = None
    attachments: list[dict] | None = None


class EmailProvider(ABC):
    """Interface para providers de email."""

    @abstractmethod
    async def send(self, message: EmailMessage) -> bool:
        """Envia email. Retorna True se sucesso."""
        pass


class SMTPProvider(EmailProvider):
    """Provider SMTP usando aiosmtplib."""

    def __init__(
        self,
        host: str,
        port: int,
        username: str,
        password: str,
        use_tls: bool = True,
    ):
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.use_tls = use_tls

    async def send(self, message: EmailMessage) -> bool:
        try:
            from email.mime.multipart import MIMEMultipart
            from email.mime.text import MIMEText

            import aiosmtplib

            msg = MIMEMultipart("alternative")
            msg["Subject"] = message.subject
            msg["From"] = f"{message.from_name or settings.app_name} <{message.from_email or self.username}>"
            msg["To"] = message.to if isinstance(message.to, str) else ", ".join(message.to)

            if message.text:
                msg.attach(MIMEText(message.text, "plain"))
            msg.attach(MIMEText(message.html, "html"))

            await aiosmtplib.send(
                msg,
                hostname=self.host,
                port=self.port,
                username=self.username,
                password=self.password,
                start_tls=self.use_tls,
            )
            return True
        except Exception as e:
            logger.error(f"Erro ao enviar email SMTP: {e}")
            return False


class SendGridProvider(EmailProvider):
    """Provider SendGrid API."""

    def __init__(self, api_key: str):
        self.api_key = api_key
        self.api_url = "https://api.sendgrid.com/v3/mail/send"

    async def send(self, message: EmailMessage) -> bool:
        try:
            recipients = message.to if isinstance(message.to, list) else [message.to]

            payload = {
                "personalizations": [{"to": [{"email": r} for r in recipients]}],
                "from": {
                    "email": message.from_email or f"noreply@{settings.app_name.lower().replace(' ', '')}.com.br",
                    "name": message.from_name or settings.app_name,
                },
                "subject": message.subject,
                "content": [
                    {"type": "text/html", "value": message.html},
                ],
            }

            if message.reply_to:
                payload["reply_to"] = {"email": message.reply_to}

            async with aiohttp.ClientSession() as session:
                async with session.post(
                    self.api_url,
                    json=payload,
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json",
                    },
                ) as response:
                    return response.status in (200, 201, 202)
        except Exception as e:
            logger.error(f"Erro ao enviar email SendGrid: {e}")
            return False


class AWSProvider(EmailProvider):
    """Provider AWS SES."""

    def __init__(self, region: str, access_key: str, secret_key: str):
        self.region = region
        self.access_key = access_key
        self.secret_key = secret_key

    async def send(self, message: EmailMessage) -> bool:
        try:
            import boto3

            ses = boto3.client(
                "ses",
                region_name=self.region,
                aws_access_key_id=self.access_key,
                aws_secret_access_key=self.secret_key,
            )

            recipients = message.to if isinstance(message.to, list) else [message.to]

            response = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: ses.send_email(
                    Source=f"{message.from_name or settings.app_name} <{message.from_email or 'noreply@vibeponto.com.br'}>",
                    Destination={"ToAddresses": recipients},
                    Message={
                        "Subject": {"Data": message.subject},
                        "Body": {
                            "Html": {"Data": message.html},
                            "Text": {"Data": message.text or ""},
                        },
                    },
                ),
            )
            return response.get("MessageId") is not None
        except Exception as e:
            logger.error(f"Erro ao enviar email AWS SES: {e}")
            return False


class ConsoleProvider(EmailProvider):
    """Provider para desenvolvimento - imprime no console."""

    async def send(self, message: EmailMessage) -> bool:
        logger.info(f"""
╔══════════════════════════════════════════════════════════════╗
║                        EMAIL (DEV)                           ║
╠══════════════════════════════════════════════════════════════╣
║ Para: {message.to}
║ Assunto: {message.subject}
╠══════════════════════════════════════════════════════════════╣
{message.html[:500]}...
╚══════════════════════════════════════════════════════════════╝
""")
        return True


class EmailService:
    """Serviço central de email."""

    def __init__(self):
        self._provider: EmailProvider | None = None

    def configure(self, provider: EmailProvider) -> None:
        """Configura o provider de email."""
        self._provider = provider

    @property
    def provider(self) -> EmailProvider:
        if self._provider is None:
            # Fallback para console em desenvolvimento
            if settings.environment == "development":
                return ConsoleProvider()
            raise RuntimeError("Email provider não configurado")
        return self._provider

    async def send(self, message: EmailMessage) -> bool:
        """Envia email."""
        return await self.provider.send(message)

    # =========================================================================
    # Templates
    # =========================================================================

    async def send_password_reset(self, email: str, token: str, nome: str) -> bool:
        """Envia email de reset de senha."""
        reset_url = f"{settings.app_public_url.rstrip('/')}/redefinir-senha?token={token}"

        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <style>
                body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
                .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
                .header {{ background: #1a56db; color: white; padding: 20px; text-align: center; }}
                .content {{ padding: 30px; background: #f9fafb; }}
                .button {{ display: inline-block; background: #1a56db; color: white; padding: 12px 24px; text-decoration: none; border-radius: 6px; margin: 20px 0; }}
                .footer {{ text-align: center; padding: 20px; color: #666; font-size: 12px; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>🕐 VibePonto</h1>
                </div>
                <div class="content">
                    <h2>Olá, {nome}!</h2>
                    <p>Recebemos uma solicitação para redefinir sua senha.</p>
                    <p>Clique no botão abaixo para criar uma nova senha:</p>
                    <a href="{reset_url}" class="button">Redefinir Senha</a>
                    <p><small>Este link expira em 1 hora.</small></p>
                    <p>Se você não solicitou esta redefinição, ignore este email.</p>
                </div>
                <div class="footer">
                    <p>© 2025 VibePonto. Todos os direitos reservados.</p>
                    <p>Este email foi enviado automaticamente, não responda.</p>
                </div>
            </div>
        </body>
        </html>
        """

        return await self.send(EmailMessage(
            to=email,
            subject="🔐 Redefinição de Senha - VibePonto",
            html=html,
        ))

    async def send_welcome(self, email: str, nome: str, senha_temporaria: str) -> bool:
        """Envia email de boas-vindas com senha temporária."""
        login_url = f"{settings.app_public_url.rstrip('/')}/login"

        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <style>
                body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
                .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
                .header {{ background: #1a56db; color: white; padding: 20px; text-align: center; }}
                .content {{ padding: 30px; background: #f9fafb; }}
                .credentials {{ background: white; padding: 15px; border-radius: 8px; margin: 20px 0; }}
                .button {{ display: inline-block; background: #1a56db; color: white; padding: 12px 24px; text-decoration: none; border-radius: 6px; margin: 20px 0; }}
                .footer {{ text-align: center; padding: 20px; color: #666; font-size: 12px; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>🕐 VibePonto</h1>
                </div>
                <div class="content">
                    <h2>Bem-vindo(a), {nome}! 🎉</h2>
                    <p>Sua conta foi criada com sucesso no VibePonto.</p>
                    <p>Use as credenciais abaixo para fazer seu primeiro acesso:</p>
                    <div class="credentials">
                        <p><strong>Email:</strong> {email}</p>
                        <p><strong>Senha temporária:</strong> {senha_temporaria}</p>
                    </div>
                    <p>⚠️ <strong>Importante:</strong> Você deverá alterar sua senha no primeiro acesso.</p>
                    <a href="{login_url}" class="button">Acessar VibePonto</a>
                </div>
                <div class="footer">
                    <p>© 2025 VibePonto. Todos os direitos reservados.</p>
                </div>
            </div>
        </body>
        </html>
        """

        return await self.send(EmailMessage(
            to=email,
            subject="🎉 Bem-vindo ao VibePonto!",
            html=html,
        ))

    async def send_marcacao_suspeita(
        self,
        gestor_email: str,
        gestor_nome: str,
        colaborador_nome: str,
        data_hora: str,
        motivo: str,
    ) -> bool:
        """Notifica gestor sobre marcação suspeita."""
        auditoria_url = f"{settings.app_public_url.rstrip('/')}/dashboard/auditoria"
        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <style>
                body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
                .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
                .header {{ background: #dc2626; color: white; padding: 20px; text-align: center; }}
                .content {{ padding: 30px; background: #f9fafb; }}
                .alert {{ background: #fef2f2; border-left: 4px solid #dc2626; padding: 15px; margin: 20px 0; }}
                .button {{ display: inline-block; background: #1a56db; color: white; padding: 12px 24px; text-decoration: none; border-radius: 6px; margin: 20px 0; }}
                .footer {{ text-align: center; padding: 20px; color: #666; font-size: 12px; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>⚠️ Marcação Suspeita</h1>
                </div>
                <div class="content">
                    <h2>Olá, {gestor_nome}!</h2>
                    <p>Uma marcação foi sinalizada como suspeita e requer sua revisão:</p>
                    <div class="alert">
                        <p><strong>Colaborador:</strong> {colaborador_nome}</p>
                        <p><strong>Data/Hora:</strong> {data_hora}</p>
                        <p><strong>Motivo:</strong> {motivo}</p>
                    </div>
                    <a href="{auditoria_url}" class="button">Revisar no Sistema</a>
                </div>
                <div class="footer">
                    <p>© 2025 VibePonto. Todos os direitos reservados.</p>
                </div>
            </div>
        </body>
        </html>
        """

        return await self.send(EmailMessage(
            to=gestor_email,
            subject="⚠️ Marcação Suspeita Detectada - VibePonto",
            html=html,
        ))

    async def send_espelho_mensal(
        self,
        email: str,
        nome: str,
        mes: str,
        ano: str,
        pdf_url: str,
    ) -> bool:
        """Envia espelho de ponto mensal."""
        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <style>
                body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
                .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
                .header {{ background: #1a56db; color: white; padding: 20px; text-align: center; }}
                .content {{ padding: 30px; background: #f9fafb; }}
                .button {{ display: inline-block; background: #1a56db; color: white; padding: 12px 24px; text-decoration: none; border-radius: 6px; margin: 20px 0; }}
                .footer {{ text-align: center; padding: 20px; color: #666; font-size: 12px; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>🕐 Espelho de Ponto</h1>
                </div>
                <div class="content">
                    <h2>Olá, {nome}!</h2>
                    <p>Seu espelho de ponto referente a <strong>{mes}/{ano}</strong> está disponível.</p>
                    <p>Acesse o sistema para visualizar e assinar o documento:</p>
                    <a href="{pdf_url}" class="button">Ver Espelho de Ponto</a>
                    <p><small>Lembre-se de assinar o espelho até o dia 5 do próximo mês.</small></p>
                </div>
                <div class="footer">
                    <p>© 2025 VibePonto. Todos os direitos reservados.</p>
                </div>
            </div>
        </body>
        </html>
        """

        return await self.send(EmailMessage(
            to=email,
            subject=f"📋 Espelho de Ponto {mes}/{ano} - VibePonto",
            html=html,
        ))


# Singleton global
email_service = EmailService()


def configure_email_service() -> None:
    """Configura o serviço de email baseado nas variáveis de ambiente."""
    import os

    provider_type = os.getenv(
        "EMAIL_PROVIDER",
        "console" if settings.environment == "development" else "disabled",
    ).lower()

    if provider_type == "sendgrid":
        api_key = os.getenv("SENDGRID_API_KEY")
        if api_key:
            email_service.configure(SendGridProvider(api_key))
        else:
            logger.warning("SendGrid email provider is missing SENDGRID_API_KEY")
    elif provider_type == "ses":
        email_service.configure(AWSProvider(
            region=os.getenv("AWS_REGION", "us-east-1"),
            access_key=os.getenv("AWS_ACCESS_KEY_ID", ""),
            secret_key=os.getenv("AWS_SECRET_ACCESS_KEY", ""),
        ))
    elif provider_type == "smtp":
        username = os.getenv("SMTP_USERNAME", "")
        password = os.getenv("SMTP_PASSWORD", "")
        if username and password:
            email_service.configure(SMTPProvider(
                host=os.getenv("SMTP_HOST", "smtp.gmail.com"),
                port=int(os.getenv("SMTP_PORT", "587")),
                username=username,
                password=password,
                use_tls=os.getenv("SMTP_USE_TLS", "true").lower() == "true",
            ))
        else:
            logger.warning("SMTP email provider is missing credentials")
    elif provider_type == "console" and settings.environment == "development":
        email_service.configure(ConsoleProvider())
    elif provider_type != "disabled":
        logger.warning("Email provider is invalid or unavailable", extra={"provider": provider_type})
