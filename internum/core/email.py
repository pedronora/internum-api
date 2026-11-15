from typing import Optional

from hostinger_mail_api import (
    ApiClient,
    Configuration,
    SendApi,
    V1SendRequest,
)

from internum.core.settings import Settings

settings = Settings()

SENDER_NAME = 'Internum - [1º SRI de Cascavel/PR]'
REQUEST_TIMEOUT_SECONDS = 10


class EmailService:
    def __init__(
        self,
        token: str = settings.HOSTINGER_MAIL_TOKEN,
        mailbox_resource_id: str = settings.HOSTINGER_MAILBOX_RESOURCE_ID,
    ):
        self.configuration = Configuration(access_token=token)
        self.mailbox_resource_id = mailbox_resource_id

    def send_email(
        self,
        email_to: list[str],
        subject: str,
        text: Optional[str] = None,
        html: Optional[str] = None,
    ) -> None:
        message = V1SendRequest(
            to=email_to,
            subject=subject,
            text=text,
            html=html,
            display_name=SENDER_NAME,
        )

        with ApiClient(self.configuration) as api_client:
            SendApi(api_client).send_email(
                self.mailbox_resource_id,
                message,
                _request_timeout=REQUEST_TIMEOUT_SECONDS,
            )
