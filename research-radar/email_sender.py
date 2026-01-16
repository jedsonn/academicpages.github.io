# research-radar/email_sender.py
"""
Email sender for Research Radar digests.
Supports: Resend, Gmail SMTP
"""
import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart


def send_with_resend(to_email: str, subject: str, html_content: str):
    """Send email using Resend API."""
    import resend

    api_key = os.environ.get("RESEND_API_KEY")
    if not api_key:
        raise ValueError("RESEND_API_KEY not set")

    resend.api_key = api_key

    response = resend.Emails.send({
        "from": "Research Radar <digest@yourdomain.com>",  # Change this
        "to": to_email,
        "subject": subject,
        "html": html_content
    })

    print(f"Email sent via Resend: {response}")
    return response


def send_with_gmail(to_email: str, subject: str, html_content: str):
    """Send email using Gmail SMTP."""
    gmail_user = os.environ.get("GMAIL_USER")
    gmail_app_password = os.environ.get("GMAIL_APP_PASSWORD")

    if not gmail_user or not gmail_app_password:
        raise ValueError("GMAIL_USER and GMAIL_APP_PASSWORD must be set")

    msg = MIMEMultipart('alternative')
    msg['Subject'] = subject
    msg['From'] = gmail_user
    msg['To'] = to_email

    html_part = MIMEText(html_content, 'html')
    msg.attach(html_part)

    with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
        server.login(gmail_user, gmail_app_password)
        server.send_message(msg)

    print(f"Email sent via Gmail to {to_email}")


def send_digest_email(to_email: str, subject: str, html_content: str, method: str = "resend"):
    """
    Send digest email using specified method.

    Args:
        to_email: Recipient email
        subject: Email subject
        html_content: HTML email body
        method: "resend" or "gmail"
    """
    if method == "resend":
        return send_with_resend(to_email, subject, html_content)
    elif method == "gmail":
        return send_with_gmail(to_email, subject, html_content)
    else:
        raise ValueError(f"Unknown email method: {method}")
