import json
import logging
import requests
from email.utils import parseaddr, formataddr
from django.conf import settings
from django.core.mail.backends.base import BaseEmailBackend

logger = logging.getLogger(__name__)

class ResendEmailBackend(BaseEmailBackend):
    """
    Custom Django Email Backend for Resend.
    Sends emails using Resend's REST API via the requests library.
    """
    def __init__(self, fail_silently=False, **kwargs):
        super().__init__(fail_silently=fail_silently, **kwargs)
        self.api_key = getattr(settings, "RESEND_API_KEY", None)
        self.from_email = getattr(settings, "RESEND_FROM_EMAIL", "onboarding@resend.dev")
        self.api_url = "https://api.resend.com/emails"

    def send_messages(self, email_messages):
        if not email_messages:
            return 0

        if not self.api_key:
            logger.error("Resend API key is not configured in settings.RESEND_API_KEY.")
            if not self.fail_silently:
                raise ValueError("Resend API key is missing.")
            return 0

        num_sent = 0
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        for message in email_messages:
            recipients = message.to
            subject = message.subject
            body = message.body

            # Parse original from email, if any
            orig_name, orig_addr = parseaddr(message.from_email)
            
            # Fallback display name
            display_name = orig_name if orig_name else "Present Sir"
            
            # Format clean from address with the Resend verified email
            from_addr = formataddr((display_name, self.from_email))

            payload = {
                "from": from_addr,
                "to": recipients,
                "subject": subject,
            }

            # Extract body depending on content type or alternatives
            if getattr(message, 'alternatives', None):
                html_content = next((alt[0] for alt in message.alternatives if alt[1] == 'text/html'), None)
                if html_content:
                    payload["html"] = html_content
                else:
                    payload["text"] = body
            elif message.content_subtype == 'html':
                payload["html"] = body
            else:
                payload["text"] = body

            try:
                response = requests.post(self.api_url, headers=headers, json=payload, timeout=15)
                if response.status_code in (200, 201):
                    num_sent += 1
                else:
                    logger.error(
                        f"Resend API email sending failed. Status code: {response.status_code}. Response: {response.text}"
                    )
                    if not self.fail_silently:
                        response.raise_for_status()
            except Exception as e:
                logger.exception(f"Error sending email through Resend: {str(e)}")
                if not self.fail_silently:
                    raise

        return num_sent
