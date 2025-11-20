from __future__ import annotations

from email.message import EmailMessage as SMTPEmailMessage
from email.utils import formataddr
from typing import Sequence

import aiosmtplib
from loguru import logger
from pydantic import EmailStr

from .config import settings
from .schemas import InternalEntity


class EmailMessage(InternalEntity):
    recipients: Sequence[EmailStr]
    subject: str
    body: str


class MailingService:
    def __init__(self) -> None:
        self._config = settings.mailing

    def _build_message(self, message: EmailMessage) -> SMTPEmailMessage:
        email = SMTPEmailMessage()
        sender = (
            formataddr((self._config.sender_name, self._config.sender_email))
            if self._config.sender_name
            else str(self._config.sender_email)
        )
        email["From"] = sender
        email["To"] = ", ".join(message.recipients)
        email["Subject"] = message.subject
        email.set_content(message.body)
        return email

    async def send(self, message: EmailMessage) -> None:
        smtp_message = self._build_message(message)
        logger.info(
            "Sending email via SMTP -> host=%s port=%s recipients=%s subject=%s",
            self._config.host,
            self._config.port,
            ",".join(message.recipients),
            message.subject,
        )
        await aiosmtplib.send(
            smtp_message,
            hostname=self._config.host,
            port=self._config.port,
            start_tls=self._config.start_tls,
            username=self._config.username,
            password=self._config.password,
        )


mailing_service = MailingService()
