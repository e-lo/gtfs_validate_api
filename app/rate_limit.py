from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from fastapi import Request
from app.settings import app_settings


# Key function for API key-based rate limiting
def get_api_key_from_request(request: Request):
    return request.headers.get("x-api-key") or get_remote_address(request)


limiter = Limiter(key_func=get_api_key_from_request, enabled=not app_settings.DISABLE_EMAIL_AND_API_KEY)

# Custom 429 handler
rate_limit_exceeded_handler = _rate_limit_exceeded_handler
