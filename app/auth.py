from fastapi import HTTPException, Header, status
from starlette.background import BackgroundTasks
import secrets
import datetime
from fastapi_mail import FastMail, MessageSchema, ConnectionConfig
from app.settings import settings
from app.firestore_db import (
    get_user, create_user, set_user_verified,
    create_api_key, get_api_key_by_value,
    create_verification_token, get_verification_token, mark_token_used
)

conf = ConnectionConfig(
    MAIL_USERNAME = settings.MAIL_USERNAME,
    MAIL_PASSWORD = settings.MAIL_PASSWORD,
    MAIL_FROM = settings.MAIL_FROM,
    MAIL_PORT = settings.MAIL_PORT,
    MAIL_SERVER = settings.MAIL_SERVER,
    MAIL_STARTTLS = settings.MAIL_STARTTLS,
    MAIL_SSL_TLS = settings.MAIL_SSL_TLS,
    USE_CREDENTIALS = True,
    VALIDATE_CERTS = True
)

# Example .env variables:
# MAIL_USERNAME=your@mailjet_api_key
# MAIL_PASSWORD=your_mailjet_secret_key
# MAIL_FROM=your_verified_sender@yourdomain.com
# MAIL_PORT=587
# MAIL_SERVER=in-v3.mailjet.com
# MAIL_STARTTLS=True
# MAIL_SSL_TLS=False

# Dependency to get DB session
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def get_api_key(x_api_key: str = Header(None)):
    if settings.DISABLE_EMAIL_AND_API_KEY:
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
    user = get_user(api_key_data['user_email'])
    if not user or not user.get('is_verified'):
        return None
    return api_key_data

def get_current_user(api_key: dict = Depends(get_api_key)):
    if not api_key:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or missing API key")
    return api_key

def create_user_with_email(email: str, background_tasks: BackgroundTasks = None):
    user = get_user(email)
    if not user:
        create_user(email, is_verified=False)
        user = get_user(email)
    if settings.DISABLE_EMAIL_AND_API_KEY:
        set_user_verified(email)
        return user
    # Create and store verification token
    token = secrets.token_urlsafe(32)
    expires_at = datetime.datetime.utcnow() + datetime.timedelta(hours=24)
    create_verification_token(email, token, expires_at)
    if background_tasks:
        send_verification_email(user, token, background_tasks)
    return user

def verify_email_token(token: str):
    vt, token_id = get_verification_token(token)
    if not vt:
        raise HTTPException(status_code=400, detail="Invalid or expired token.")
    if vt['expires_at'] < datetime.datetime.utcnow():
        raise HTTPException(status_code=400, detail="Token expired.")
    mark_token_used(token_id)
    set_user_verified(vt['user_email'])
    # Generate API key and return it
    api_key_value = secrets.token_urlsafe(32)
    create_api_key(vt['user_email'], api_key_value)
    return get_user(vt['user_email']), type('APIKey', (), {'key': api_key_value})

def send_verification_email(user: dict, token: str, background_tasks: BackgroundTasks):
    verify_url = f"{settings.BASE_URL}/verify-email?token={token}"
    subject = "Verify your email for GTFS Validator API"
    body = f"""
    <h2>Verify your email</h2>
    <p>Click the link below to verify your email and receive your API key:</p>
    <a href='{verify_url}'>{verify_url}</a>
    <p>This link will expire in 24 hours.</p>
    """
    message = MessageSchema(
        subject=subject,
        recipients=[user['email'] if 'email' in user else user.get('user_email')],
        body=body,
        subtype="html"
    )
    fm = FastMail(conf)
    background_tasks.add_task(fm.send_message, message) 