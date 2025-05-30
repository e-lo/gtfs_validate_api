import os
from pydantic_settings import BaseSettings, SettingsConfigDict

env = os.getenv("APP_ENV", "local")
env_file = {
    "local": ".env",
    "development": ".env.development",
    "production": ".env.production"
}.get(env, ".env")

class Settings(BaseSettings):
    BASE_URL: str = "http://localhost:8080"
    DISABLE_EMAIL_AND_API_KEY: bool = False
    MAIL_USERNAME: str
    MAIL_PASSWORD: str
    MAIL_FROM: str
    MAIL_PORT: int = 587
    MAIL_SERVER: str = "smtp.gmail.com"
    MAIL_STARTTLS: bool = True
    MAIL_SSL_TLS: bool = False
    model_config = SettingsConfigDict(env_file=env_file, env_file_encoding="utf-8")

settings = Settings() 