from fastapi import FastAPI, UploadFile, HTTPException, Form, Query, Response, File, Request, Depends
from fastapi.responses import JSONResponse, HTMLResponse
from fastapi.templating import Jinja2Templates
from slowapi.util import get_remote_address
from typing import Optional
import subprocess
import tempfile
import json
import aiohttp
import markdown  # type: ignore
from pathlib import Path
from starlette.background import BackgroundTasks
import re
import logging

from app.rate_limit import limiter, rate_limit_exceeded_handler
from app.auth import get_api_key, create_user_with_email, verify_email_token
from app.settings import app_settings, rate_limit_settings

JAR = "/opt/gtfs-validator.jar"

app = FastAPI(
    title="GTFS Validator API",
    version="1.0.0-beta.1",
    description="API wrapper for MobilityData GTFS Validator",
    docs_url="/docs",
)

# Add slowapi middleware and exception handler
app.state.limiter = limiter

app.add_exception_handler(429, rate_limit_exceeded_handler)  # type: ignore[arg-type]

# Jinja2 templates for landing page
templates = Jinja2Templates(directory="app/templates")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@app.get("/", response_class=HTMLResponse)
def landing(request: Request):
    logger.info(f"Landing page accessed from {request.client.host}")
    # Render README.md as HTML
    readme_path = Path(__file__).parent.parent / "README.md"
    try:
        readme_md = readme_path.read_text(encoding="utf-8")
        readme_html = markdown.markdown(readme_md, extensions=["fenced_code", "tables"])
    except Exception as e:
        readme_html = f"<p>Could not load README.md: {e}</p>"
    return templates.TemplateResponse("landing.html", {"request": request, "readme_html": readme_html})

@app.post("/request-key")
def request_key(request: Request, background_tasks: BackgroundTasks, email: str = Form(...)):
    logger.info(f"API key request for email: {email} from {request.client.host}")
    try:
        user = create_user_with_email(email, background_tasks)
        logger.info(f"User created or found for email: {email}")
        return templates.TemplateResponse("landing.html", {"request": request, "readme_html": "<p>Check your email for a verification link.</p>"})
    except Exception as e:
        logger.error(f"Error processing API key request for {email}: {e}")
        return templates.TemplateResponse("landing.html", {"request": request, "readme_html": f"<p>Error: {e}</p>"})

def run_validator(feed_path: str, work: str) -> None:
    result = subprocess.run(
        ["java", "-jar", JAR, "-i", str(feed_path), "-o", str(work)],
        capture_output=True, text=True
    )
    if result.returncode != 0:
        raise HTTPException(500, result.stderr)

def get_report(work: str, format: str):
    work_path = Path(work)
    report_json_path = work_path / "report.json"
    report_html_path = work_path / "report.html"
    if format == "json":
        with report_json_path.open() as f:
            return json.load(f)
    elif format == "html":
        if not report_html_path.exists():
            raise HTTPException(500, "HTML report not found.")
        with report_html_path.open() as f:
            return Response(f.read(), media_type="text/html")
    elif format == "errors":
        with report_json_path.open() as f:
            data = json.load(f)
        errors = [n for n in data.get("notices", []) if n.get("severity") == "ERROR"]
        return JSONResponse({"errors": errors})
    else:
        raise HTTPException(400, "Invalid format parameter.")

async def save_uploaded_file(file: UploadFile, dest: str):
    if file.content_type != "application/zip":
        raise HTTPException(400, "GTFS feed must be a .zip")
    dest_path = Path(dest)
    dest_path.write_bytes(await file.read())

async def download_file(url: str, dest: str):
    if not url.lower().endswith(".zip"):
        raise HTTPException(400, "A valid GTFS .zip URL must be provided.")
    dest_path = Path(dest)
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as resp:
            if resp.status != 200:
                raise HTTPException(400, f"Failed to download file: {resp.status}")
            with dest_path.open("wb") as out:
                while True:
                    chunk = await resp.content.read(1024 * 1024)
                    if not chunk:
                        break
                    out.write(chunk)

def get_rate_limit(request: Request, api_key=Depends(get_api_key)):
    if api_key:
        return rate_limit_settings.AUTH_LIMIT
    else:
        return rate_limit_settings.UNAUTH_LIMIT

@app.post("/validate")
@limiter.limit("{rate_limit}", key_func=get_remote_address)
async def validate(
    request: Request,
    file: Optional[UploadFile] = File(None),
    url: Optional[str] = Form(None),
    format: str = Query("json", enum=["json", "html", "errors"], description="Response format: 'json' (default), 'html', or 'errors'"),
    api_key = Depends(get_api_key),
    rate_limit: str = Depends(get_rate_limit),
):
    logger.info(f"/validate called from {request.client.host} with api_key={bool(api_key)}")
    try:
        if app_settings.DISABLE_EMAIL_AND_API_KEY:
            logger.info("DISABLE_EMAIL_AND_API_KEY is set; skipping auth and rate limiting.")
        if isinstance(file, str) and file == "":
            file = None
        if not file and not url:
            logger.warning("No file or URL provided to /validate.")
            raise HTTPException(400, "You must provide either a file or a URL.")
        if file and url:
            logger.warning("Both file and URL provided to /validate.")
            raise HTTPException(400, "Provide only one of file or URL, not both.")
        with tempfile.TemporaryDirectory() as work:
            work_path = Path(work)
            feed = work_path / "feed.zip"
            if file:
                await save_uploaded_file(file, str(feed))
                logger.info(f"Uploaded file saved for validation: {file.filename}")
            else:
                if url is None:
                    logger.warning("No URL provided when file is None.")
                    raise HTTPException(400, "You must provide a URL if no file is uploaded.")
                await download_file(url, str(feed))
                logger.info(f"Downloaded file from URL: {url}")
            run_validator(str(feed), str(work_path))
            logger.info("Validation completed successfully.")
            return get_report(str(work_path), format)
    except Exception as e:
        logger.error(f"Error in /validate: {e}")
        raise

@app.get("/verify-email", response_class=HTMLResponse)
def verify_email(request: Request, token: str):
    api_key_value = None
    try:
        user, api_key = verify_email_token(token)
        api_key_value = api_key.key
        msg = "<h2>Email verified!</h2>"
    except Exception as e:
        msg = f"<h2>Verification failed</h2><p>{e}</p>"
    # Extract usage instructions from README
    readme_path = Path(__file__).parent.parent / "README.md"
    usage_html = ""
    try:
        readme_md = readme_path.read_text(encoding="utf-8")
        # Extract from ## Programmatic Usage to the next ##
        usage = re.search(r"## Usage(.+?)(^## |\Z)", readme_md, re.DOTALL | re.MULTILINE)
        combined = ""
        if usage:
            combined += "## Programmatic Usage" + usage.group(1)
        if combined:
            usage_html = markdown.markdown(combined, extensions=["fenced_code", "tables"])
    except Exception as e:
        usage_html = f"<p>Could not load usage instructions: {e}</p>"
    return templates.TemplateResponse("verify_email.html", {"request": request, "message": msg, "api_key": api_key_value, "usage_html": usage_html})