import logging
from flask import current_app

def _console_send_reset(email: str, token: str):
    url = f"https://frontend-app/reset-password?token={token}"
    logging.info(f"[MAIL][RESET] To={email}, URL={url}")
    return True

def _console_send_verify(email: str, token: str):
    url = f"https://frontend-app/verify-email?token={token}"
    logging.info(f"[MAIL][VERIFY] To={email}, URL={url}")
    return True

def send_reset_password(email: str, token: str):
    fn = current_app.config.get("MAILER_SEND_RESET_FUNC", _console_send_reset)
    return fn(email, token)

def send_verify_email(email: str, token: str):
    fn = current_app.config.get("MAILER_SEND_VERIFY_FUNC", _console_send_verify)
    return fn(email, token)