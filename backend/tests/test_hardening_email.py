"""Public application links used in transactional email templates."""

import pytest

from app.core.email import EmailMessage, EmailProvider, EmailService

pytestmark = pytest.mark.asyncio


class CapturingProvider(EmailProvider):
    def __init__(self):
        self.messages: list[EmailMessage] = []

    async def send(self, message: EmailMessage) -> bool:
        self.messages.append(message)
        return True


async def test_email_links_use_configured_public_app_url(monkeypatch):
    monkeypatch.setattr("app.core.email.settings.app_public_url", "https://vibeponto.com.br/")
    provider = CapturingProvider()
    service = EmailService()
    service.configure(provider)

    await service.send_password_reset("user@example.com", "reset-token", "User")
    await service.send_welcome("user@example.com", "User", "temporary-password")
    await service.send_marcacao_suspeita(
        "manager@example.com",
        "Manager",
        "User",
        "2026-09-29 12:00",
        "Test",
    )

    assert "https://vibeponto.com.br/redefinir-senha?token=reset-token" in provider.messages[0].html
    assert "https://vibeponto.com.br/login" in provider.messages[1].html
    assert "https://vibeponto.com.br/dashboard/auditoria" in provider.messages[2].html
