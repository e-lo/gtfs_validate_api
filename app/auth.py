from fastapi import HTTPException, Header, status, Depends
from starlette.background import BackgroundTasks
import secrets
import datetime
from fastapi_mail import FastMail, MessageSchema, ConnectionConfig
from app.settings import app_settings, mail_settings
from typing import Optional
import logging

logger = logging.getLogger(__name__)

# Only import Firestore-dependent functions if needed
if not app_settings.DISABLE_EMAIL_AND_API_KEY:
    from app.firestore_db import (
        get_user, create_user, set_user_verified,
        create_api_key, get_api_key_by_value,
        create_verification_token, get_verification_token, mark_token_used
    )
else:
    get_user = create_user = set_user_verified = create_api_key = get_api_key_by_value = create_verification_token = get_verification_token = mark_token_used = lambda *args, **kwargs: None

# Only require mail settings if email/API key is enabled
if not app_settings.DISABLE_EMAIL_AND_API_KEY:
    if mail_settings is None:
        print("SETTINGS:", app_settings)
        if app_settings.APP_ENV != "local":
            raise RuntimeError("Mail settings must be set in non-local environments.")
        else:
            raise RuntimeError("Authorization is disabled in local environment.")

    conf = ConnectionConfig(
        MAIL_USERNAME = mail_settings.MAIL_USERNAME,
        MAIL_PASSWORD = mail_settings.MAIL_PASSWORD,
        MAIL_FROM = mail_settings.MAIL_FROM,
        MAIL_PORT = mail_settings.MAIL_PORT,    
        MAIL_SERVER = mail_settings.MAIL_SERVER,
        MAIL_STARTTLS = mail_settings.MAIL_STARTTLS,
        MAIL_SSL_TLS = mail_settings.MAIL_SSL_TLS,
        USE_CREDENTIALS = True,
        VALIDATE_CERTS = True
    )
else:
    conf = None

# Example .env variables:
# MAIL_USERNAME=your@mailjet_api_key
# MAIL_PASSWORD=your_mailjet_secret_key
# MAIL_FROM=your_verified_sender@yourdomain.com
# MAIL_PORT=587
# MAIL_SERVER=in-v3.mailjet.com
# MAIL_STARTTLS=True
# MAIL_SSL_TLS=False

def get_api_key(x_api_key: str = Header(None)):
    if app_settings.DISABLE_EMAIL_AND_API_KEY:
        # Bypass: always return a dummy APIKey-like dict
        user = get_user("dummy@localhost")
        if not user:
            create_user("dummy@localhost", is_verified=True)
            user = get_user("dummy@localhost")
        # Create a dummy API key if needed
        dummy_key = "dummy-key"
        api_key_data = get_api_key_by_value(dummy_key)
        if not api_key_data:
            create_api_key("dummy@localhost", dummy_key)
            api_key_data = get_api_key_by_value(dummy_key)
        return api_key_data
    if not x_api_key:
        return None
    api_key_data = get_api_key_by_value(x_api_key)
    if not api_key_data:
        return None
    user = get_user(api_key_data["user_email"])
    if not user or not user.get("is_verified"):
        return None
    return api_key_data


def get_current_user(api_key: dict = Depends(get_api_key)):
    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API key",
        )
    return api_key


def create_user_with_email(
    email: str, background_tasks: Optional[BackgroundTasks] = None
):
    logger.info(f"create_user_with_email called for {email}")
    user = get_user(email)
    if not user:
        create_user(email, is_verified=False)
        logger.info(f"Created new user for {email}")
        user = get_user(email)
    if app_settings.DISABLE_EMAIL_AND_API_KEY:
        set_user_verified(email)
        logger.info(f"Authorization disabled; user {email} auto-verified.")
        return user
    # Create and store verification token
    token = secrets.token_urlsafe(32)
    expires_at = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(
        hours=24
    )
    create_verification_token(email, token, expires_at)
    logger.info(f"Verification token created for {email}")
    if background_tasks:
        send_verification_email(user, token, background_tasks)
        logger.info(f"Verification email sent to {email}")
    return user


def verify_email_token(token: str):
    logger.info(f"verify_email_token called for token: {token}")
    vt, token_id = get_verification_token(token)
    if not vt:
        logger.error(f"Invalid or expired token: {token}")
        raise HTTPException(status_code=400, detail="Invalid or expired token.")
    expires_at = vt["expires_at"]
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=datetime.timezone.utc)
    now = datetime.datetime.now(datetime.timezone.utc)
    if expires_at < now:
        logger.error(f"Token expired for user {vt['user_email']}")
        raise HTTPException(status_code=400, detail="Token expired.")
    mark_token_used(token_id)
    set_user_verified(vt["user_email"])
    logger.info(f"User {vt['user_email']} verified via token.")
    api_key_value = secrets.token_urlsafe(32)
    create_api_key(vt["user_email"], api_key_value)
    logger.info(f"API key created for user {vt['user_email']}")
    return get_user(vt["user_email"]), type("APIKey", (), {"key": api_key_value})


def send_verification_email(user: dict, token: str, background_tasks: BackgroundTasks):
    logger.info(
        f"send_verification_email called for {user.get('email') or user.get('user_email')}"
    )
    verify_url = f"{app_settings.BASE_URL}/verify-email?token={token}"
    subject = "Verify your email for GTFS Validator API"
    body = f"""
    <h2>Verify your email</h2>
    <p>Click the link below to verify your email and receive your API key:</p>
    <a href='{verify_url}'>{verify_url}</a>
    <p>This link will expire in 24 hours.</p>
    """
    recipients = [user["email"]] if "email" in user else [user.get("user_email")]
    message = MessageSchema(
        subject=subject,
        recipients=recipients,
        body=body,
        subtype="html",  # type: ignore[arg-type]
    )
    fm = FastMail(conf)
    background_tasks.add_task(fm.send_message, message)
    logger.info(f"Verification email task added for {recipients}")
