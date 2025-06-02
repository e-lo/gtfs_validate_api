from pydantic_settings import BaseSettings
from typing import Literal, Annotated, Optional
from pydantic import SecretStr, StringConstraints

r_rate_limit = r"^\d+/(second|minute|hour|day|week|month)$"


class AppSettings(BaseSettings):
    BASE_URL: str = "http://localhost:8080"
    DISABLE_EMAIL_AND_API_KEY: bool = False
    APP_ENV: Literal["local", "development", "production", "default"] = "default"


class MailSettings(BaseSettings):
    MAIL_USERNAME: str
    MAIL_PASSWORD: SecretStr
    MAIL_FROM: str
    MAIL_PORT: int
    MAIL_SERVER: str
    MAIL_STARTTLS: bool
    MAIL_SSL_TLS: bool

class RateLimitSettings(BaseSettings):
    UNAUTH_LIMIT: Annotated[str, StringConstraints(pattern=r_rate_limit)] = "5/day"
    AUTH_LIMIT: Annotated[str, StringConstraints(pattern=r_rate_limit)] = "50/day"

app_settings = AppSettings()
mail_settings: Optional[MailSettings] = MailSettings() if not app_settings.DISABLE_EMAIL_AND_API_KEY else None
rate_limit_settings: Optional[RateLimitSettings] = RateLimitSettings() if not app_settings.DISABLE_EMAIL_AND_API_KEY else None
