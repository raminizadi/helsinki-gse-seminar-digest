"""Send emails via SendGrid API."""

from __future__ import annotations

import logging
import os

from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Header, Mail

logger = logging.getLogger(__name__)


def send_digest(
    to_email: str,
    subject: str,
    html_content: str,
    unsubscribe_url: str = "#",
) -> bool:
    """Send a digest email via SendGrid.

    Returns True on success, False on failure.
    """
    api_key = os.environ["SENDGRID_API_KEY"]
    from_email = os.environ["EMAIL_FROM"]

    message = Mail(
        from_email=from_email,
        to_emails=to_email,
        subject=subject,
        html_content=html_content,
    )
    # List-Unsubscribe header for email client "unsubscribe" buttons
    if unsubscribe_url and unsubscribe_url != "#":
        message.header = Header("List-Unsubscribe", f"<{unsubscribe_url}>")

    try:
        sg = SendGridAPIClient(api_key)
        response = sg.send(message)
        logger.info(
            "Email sent to %s — status %d", to_email, response.status_code
        )
        return response.status_code in (200, 201, 202)
    except Exception:
        logger.exception("Failed to send email to %s", to_email)
        return False


def send_confirmation(to_email: str, confirm_url: str) -> bool:
    """Send a double opt-in confirmation email. Returns True on success."""
    api_key = os.environ["SENDGRID_API_KEY"]
    from_email = os.environ["EMAIL_FROM"]

    html_content = f"""\
<div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; max-width: 480px; margin: 0 auto; padding: 32px;">
  <h2 style="color: #1a365d; margin-top: 0;">Confirm your subscription</h2>
  <p>You requested to receive weekly Helsinki GSE seminar updates.</p>
  <p>
    <a href="{confirm_url}"
       style="display: inline-block; background: #1a365d; color: #ffffff;
              padding: 12px 24px; border-radius: 4px; text-decoration: none;
              font-weight: 500;">
      Confirm subscription
    </a>
  </p>
  <p style="color: #718096; font-size: 13px; margin-top: 24px;">
    If you didn't request this, you can safely ignore this email.
  </p>
</div>"""

    message = Mail(
        from_email=from_email,
        to_emails=to_email,
        subject="Confirm your Helsinki GSE seminar subscription",
        html_content=html_content,
    )

    try:
        sg = SendGridAPIClient(api_key)
        response = sg.send(message)
        logger.info(
            "Confirmation email sent to %s — status %d",
            to_email,
            response.status_code,
        )
        return response.status_code in (200, 201, 202)
    except Exception:
        logger.exception("Failed to send confirmation email to %s", to_email)
        return False
