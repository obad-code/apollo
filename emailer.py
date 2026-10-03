"""Apollo's email: alerts to you, and a message you ask him to send.

Gmail, over SMTP with an app password - the simplest way that works with no
server and no Google Cloud project:

    1. Turn on 2-Step Verification on the Google account.
    2. https://myaccount.google.com/apppasswords -> create one called Apollo.
    3. setx APOLLO_SMTP_USER "you@gmail.com"
       setx APOLLO_SMTP_PASSWORD "the 16 letters, no spaces"
       setx APOLLO_ALERT_TO "you@gmail.com"     (optional; defaults to the user)

The password is read from the environment and only ever sent to Gmail.
Another provider works too: APOLLO_SMTP_HOST and APOLLO_SMTP_PORT (SSL).
"""

import html
import logging
import os
import smtplib
import ssl
from email.message import EmailMessage
from email.utils import formataddr

log = logging.getLogger("apollo.email")

HOST = "smtp.gmail.com"
PORT = 465


def settings():
    user = (os.environ.get("APOLLO_SMTP_USER") or "").strip()
    password = (os.environ.get("APOLLO_SMTP_PASSWORD") or "").replace(" ", "").strip()
    if not user or not password:
        return None
    return {"user": user, "password": password,
            "to": (os.environ.get("APOLLO_ALERT_TO") or user).strip(),
            "host": os.environ.get("APOLLO_SMTP_HOST") or HOST,
            "port": int(os.environ.get("APOLLO_SMTP_PORT") or PORT)}


def ready():
    return settings() is not None


def compose(sender, to, subject, text, rich=None):
    """The message: plain text, and an HTML part when `rich` is given."""
    message = EmailMessage()
    message["From"] = formataddr(("Apollo", sender))
    message["To"] = to
    message["Subject"] = " ".join(str(subject or "").split())[:200] or "From Apollo"
    message.set_content(str(text or ""))
    if rich:
        message.add_alternative(rich, subtype="html")
    return message


def _deliver(found, message):
    """The one connection to the mail server. Tests replace this."""
    with smtplib.SMTP_SSL(found["host"], found["port"], context=ssl.create_default_context(),
                          timeout=20) as server:
        server.login(found["user"], found["password"])
        server.send_message(message)


def send(subject, text, to=None, rich=None):
    """Send one email. `to` defaults to you. Raises with a sentence if it cannot."""
    found = settings()
    if found is None:
        raise RuntimeError("Email is not set up (APOLLO_SMTP_USER and APOLLO_SMTP_PASSWORD).")
    to = (to or found["to"]).strip()
    if "@" not in to or any(c in to for c in "\r\n,;"):
        raise ValueError("That is not one email address.")
    try:
        _deliver(found, compose(found["user"], to, subject, text, rich))
    except smtplib.SMTPAuthenticationError as e:
        raise RuntimeError("Gmail refused the login - the app password may be wrong.") from e
    except (smtplib.SMTPException, OSError) as e:
        raise RuntimeError(f"The email did not go: {type(e).__name__}.") from e
    log.info("email sent to %s", to.split("@")[-1])
    return {"to": to}


def card(title, lines, link="", accent="#F5B83D"):
    """A small dark HTML card for an alert, in Apollo's colours."""
    body = "".join(f"<p style='margin:0 0 10px;line-height:1.5'>{html.escape(line)}</p>"
                   for line in lines if line)
    button = (f"<p style='margin:18px 0 0'><a href='{html.escape(link)}' style='color:{accent};"
              f"text-decoration:none;font-weight:600'>Read the story →</a></p>" if link else "")
    return (f"<div style='background:#0b0b0f;padding:24px;font-family:Segoe UI,Arial,sans-serif'>"
            f"<div style='max-width:560px;margin:auto;background:#14141a;border:1px solid #2a2a33;"
            f"border-radius:16px;padding:22px;color:#e9e9ee'>"
            f"<div style='font-size:11px;letter-spacing:.14em;color:{accent};margin-bottom:8px'>"
            f"APOLLO · MARKET ALERT</div>"
            f"<h2 style='margin:0 0 14px;font-size:19px;color:#fff'>{html.escape(title)}</h2>"
            f"{body}{button}</div></div>")
