import logging
import smtplib
from dataclasses import dataclass
from email.message import EmailMessage
from email.utils import formataddr
from textwrap import dedent

from app.core.config import get_settings
from app.core.exceptions import ExternalDependencyError
from app.schemas.contact import ContactRequest

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ContactDeliveryResult:
    delivery_mode: str
    message: str


class ContactService:
    def __init__(self) -> None:
        self.settings = get_settings()

    def submit(self, payload: ContactRequest) -> ContactDeliveryResult:
        self._ensure_email_delivery_is_configured()
        messages = self._build_messages(payload)

        try:
            self._send_messages(messages)
        except (smtplib.SMTPException, OSError) as exc:
            logger.exception("SMTP delivery failed.")
            raise ExternalDependencyError(
                "Contact delivery failed while sending email.",
                details={"provider": "smtp", "error_type": type(exc).__name__},
            ) from exc

        if payload.email:
            return ContactDeliveryResult(
                delivery_mode="owner_and_sender_notified",
                message=(
                    "Your message has been delivered to Yasaswini's inbox, and a confirmation email has been sent to you."
                ),
            )

        return ContactDeliveryResult(
            delivery_mode="owner_notified_only",
            message=(
                "Your message has been delivered to Yasaswini's inbox. Since you chose phone-only contact, she will follow up directly."
            ),
        )

    def _get_from_email(self) -> str:
        return self.settings.smtp_from_email or self.settings.smtp_username or self.settings.contact_receiver_email

    def _ensure_email_delivery_is_configured(self) -> None:
        required = {
            "smtp_host": self.settings.smtp_host,
            "contact_receiver_email": self.settings.contact_receiver_email,
        }
        missing = [key for key, value in required.items() if not value]
        if missing:
            raise ExternalDependencyError(
                "Contact email is not configured yet.",
                details={"missing_settings": missing},
            )

    def _build_messages(self, payload: ContactRequest) -> list[EmailMessage]:
        from_email = self._get_from_email()
        owner_message = EmailMessage()
        owner_message["From"] = formataddr((self.settings.smtp_from_name, from_email))
        owner_message["To"] = self.settings.contact_receiver_email
        owner_message["Subject"] = self._build_owner_subject(payload)
        if payload.email:
            owner_message["Reply-To"] = payload.email
        owner_message.set_content(self._build_owner_body(payload))

        messages = [owner_message]

        if payload.email:
            sender_message = EmailMessage()
            sender_message["From"] = formataddr((self.settings.smtp_from_name, from_email))
            sender_message["To"] = payload.email
            sender_message["Subject"] = self._build_sender_subject(payload)
            sender_message.set_content(self._build_sender_body(payload))
            messages.append(sender_message)

        return messages

    def _send_messages(self, messages: list[EmailMessage]) -> None:
        if self.settings.smtp_use_ssl:
            server = smtplib.SMTP_SSL(
                self.settings.smtp_host,
                self.settings.smtp_port,
                timeout=self.settings.smtp_timeout_seconds,
            )
        else:
            server = smtplib.SMTP(
                self.settings.smtp_host,
                self.settings.smtp_port,
                timeout=self.settings.smtp_timeout_seconds,
            )

        with server:
            if not self.settings.smtp_use_ssl and self.settings.smtp_use_starttls:
                server.starttls()

            if self.settings.smtp_username and self.settings.smtp_password:
                server.login(self.settings.smtp_username, self.settings.smtp_password)

            for message in messages:
                server.send_message(message)

    @staticmethod
    def _build_owner_subject(payload: ContactRequest) -> str:
        company = payload.company or "Independent recruiter or collaborator"
        return f"Portfolio inquiry | {payload.name} | {company}"

    def _build_owner_body(self, payload: ContactRequest) -> str:
        return dedent(
            f"""
            A new portfolio inquiry was submitted for {self.settings.contact_owner_name}.

            Profile summary:
            {self.settings.contact_owner_name} is a software engineer focused on Java and Python backend systems,
            AI-enabled services, secure APIs, microservices, and cloud-native delivery. Recent work includes
            production ML inference services, OAuth2 and JWT-secured APIs, and distributed systems tuned for
            measurable reliability and performance.

            Contact details:
            Name: {payload.name}
            Company: {payload.company or "Not provided"}
            Email: {payload.email or "Not provided"}
            Phone: {payload.phone or "Not provided"}
            Subject: {payload.subject}
            Preferred follow-up: {"Email" if payload.email else "Phone"}

            Message:
            {payload.message}

            Suggested response angle:
            - Backend and platform engineering roles
            - AI-enabled services and inference-backed product workflows
            - Secure API and distributed systems work with strong product communication
            """
        ).strip()

    @staticmethod
    def _build_sender_subject(payload: ContactRequest) -> str:
        return f"Thanks for reaching out to Yasaswini Adivanne | {payload.subject}"

    def _build_sender_body(self, payload: ContactRequest) -> str:
        return dedent(
            f"""
            Hi {payload.name},

            Thank you for reaching out through Yasaswini Adivanne's portfolio.

            Your message has been delivered successfully. Yasaswini is a software engineer with experience across
            Java and Python backend systems, AI-enabled services, secure microservices, cloud-native deployment,
            and full-stack engineering delivery. She reviews opportunities related to backend, platform, and
            product-focused software engineering.

            Submission summary:
            Subject: {payload.subject}
            Company: {payload.company or "Not provided"}
            Phone: {payload.phone or "Not provided"}
            Message:
            {payload.message}

            If your note is about a software engineering opportunity, collaboration, or portfolio discussion,
            this inbox is monitored for direct follow-up.

            Regards,
            Portfolio Contact
            """
        ).strip()
