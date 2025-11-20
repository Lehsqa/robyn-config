from typing import Sequence

from pydantic import EmailStr

from ..application import InternalEntity


class EmailMessage(InternalEntity):
    recipients: Sequence[EmailStr]
    subject: str
    body: str
