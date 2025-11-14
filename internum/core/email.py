import mailtrap as mt

from internum.core.settings import Settings

settings = Settings()


class EmailService:
    def __init__(self, token: str = settings.MAILTRAP_TOKEN):
        self.client = mt.MailtrapClient(token=token)
        self.sender = mt.Address(
            email='internum@marconnora.com',
            name='Internum - [1º SRI de Cascavel/PR]',
        )

    def send_email(
        self,
        email_to: list[str],
        subject: str,
        text: str = None,
        html: str = None,
        category: str = 'General',
    ):
        recipients = [mt.Address(email=email) for email in email_to]

        mail = mt.Mail(
            sender=self.sender,
            to=recipients,
            subject=subject,
            text=text,
            html=html,
            category=category,
        )

        response = self.client.send(mail)
        return response
