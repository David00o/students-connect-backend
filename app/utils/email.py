import logging
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import aiosmtplib

from app.core.config import settings

logger = logging.getLogger(__name__)


async def send_email(*, to: str, subject: str, html_body: str) -> None:
    """Send an HTML email via SMTP. Logs and re-raises on failure."""
    message = MIMEMultipart("alternative")
    message["From"] = f"{settings.EMAIL_FROM_NAME} <{settings.EMAIL_FROM}>"
    message["To"] = to
    message["Subject"] = subject
    message.attach(MIMEText(html_body, "html"))

    try:
        await aiosmtplib.send(
            message,
            hostname=settings.SMTP_HOST,
            port=settings.SMTP_PORT,
            username=settings.SMTP_USERNAME,
            password=settings.SMTP_PASSWORD,
            start_tls=True,
        )
        logger.info("Email sent to %s | subject: %s", to, subject)
    except Exception as exc:
        logger.error("Failed to send email to %s: %s", to, exc)
        raise


def _otp_html(otp_code: str, title: str, body_text: str) -> str:
    return f"""
    <!DOCTYPE html>
    <html>
    <body style="font-family: Arial, sans-serif; background: #f4f4f4; padding: 30px;">
      <div style="max-width: 480px; margin: auto; background: #fff;
                  border-radius: 8px; padding: 32px;">
        <h2 style="color: #1a1a1a;">{title}</h2>
        <p style="color: #444;">{body_text}</p>
        <div style="text-align: center; margin: 32px 0;">
          <span style="font-size: 36px; font-weight: bold; letter-spacing: 8px;
                       color: #4f46e5;">{otp_code}</span>
        </div>
        <p style="color: #888; font-size: 13px;">
          This OTP expires in {settings.OTP_EXPIRE_MINUTES} minutes.
          If you did not request this, please ignore this email.
        </p>
      </div>
    </body>
    </html>
    """


async def send_verification_otp(to: str, otp_code: str) -> None:
    await send_email(
        to=to,
        subject="Verify your Students Connect account",
        html_body=_otp_html(
            otp_code,
            title="Email Verification",
            body_text="Use the OTP below to verify your email address.",
        ),
    )


async def send_password_reset_otp(to: str, otp_code: str) -> None:
    await send_email(
        to=to,
        subject="Reset your Students Connect password",
        html_body=_otp_html(
            otp_code,
            title="Password Reset",
            body_text="Use the OTP below to reset your password.",
        ),
    )
