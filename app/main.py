from fastapi import FastAPI, UploadFile, HTTPException, Form, Query, Response, Security, File
from fastapi.responses import JSONResponse
from fastapi.security.api_key import APIKeyHeader # For defining API key location
from fastapi.openapi.utils import get_openapi
from typing import Optional
import subprocess
import tempfile
import json
import os
import aiohttp

JAR = "/opt/gtfs-validator.jar"

APP_URL = "https://gtfs-validator-67226885558.us-central1.run.app"
GLOBAL_SECURITY_SCHEME = { 
    "ApiKeyAuth": {
        "type": "apiKey",
        "in": "header",
        "name": "X-API-KEY"
    }
}
X_GOOGLE_MANAGEMENT_METRICS = [{
    "name": "validation-requests",
    "displayName": "Validadtion Requests",
    "valueType": "INT64", # required to be INT64
    "metricKind": "DELTA" # required to be delta
}]
X_GOOGLE_QUOTAS = {
    "limits": [
        {
            "name": "registered-requests-limit",
            "metric": "validation-requests",
            "unit": "1/min/{project}", # Or other appropriate unit
            "values": {"STANDARD": 60} # Example: 60 req/min for API key users
        },
        {
            "name": "unregistered-requests-limit",
            "metric": "validation-requests",
            "unit": "1/min/{project}",
            "values": {"STANDARD": 1} # Example: 10 req/min for public
        }
    ]
}

# Define your API Key security scheme (name can be anything, e.g., X-API-KEY)
# auto_error=False if you want to handle missing key manually or let API Gateway do it
api_key_header_scheme = APIKeyHeader(name="X-API-KEY", auto_error=False) 


app = FastAPI(
    title="GTFS Validator API",
    version="1.0.0-beta.1",
    description="API wrapper for MobilityData GTFS Validator",
    docs_url="/docs",
)

def run_validator(feed_path: str, work: str) -> None:
    result = subprocess.run(
        ["java", "-jar", JAR, "-i", feed_path, "-o", work],
        capture_output=True, text=True
    )
    if result.returncode != 0:
        raise HTTPException(500, result.stderr)

def get_report(work: str, format: str):
    report_json_path = os.path.join(work, "report.json")
    report_html_path = os.path.join(work, "report.html")
    if format == "json":
        with open(report_json_path) as f:
            return json.load(f)
    elif format == "html":
        if not os.path.exists(report_html_path):
            raise HTTPException(500, "HTML report not found.")
        with open(report_html_path) as f:
            return Response(f.read(), media_type="text/html")
    elif format == "errors":
        with open(report_json_path) as f:
            data = json.load(f)
        errors = [n for n in data.get("notices", []) if n.get("severity") == "ERROR"]
        return JSONResponse({"errors": errors})
    else:
        raise HTTPException(400, "Invalid format parameter.")

async def save_uploaded_file(file: UploadFile, dest: str):
    if file.content_type != "application/zip":
        raise HTTPException(400, "GTFS feed must be a .zip")
    with open(dest, "wb") as out:
        out.write(await file.read())

async def download_file(url: str, dest: str):
    if not url.lower().endswith(".zip"):
        raise HTTPException(400, "A valid GTFS .zip URL must be provided.")
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as resp:
            if resp.status != 200:
                raise HTTPException(400, f"Failed to download file: {resp.status}")
            with open(dest, "wb") as out:
                while True:
                    chunk = await resp.content.read(1024 * 1024)
                    if not chunk:
                        break
                    out.write(chunk)

@app.post("/validate",
        openapi_extra={
            "x-google-backend": {
                "address": APP_URL,
            },
            "x-google-quota": {
                "metricCosts": 1
            },
            "operationId": "validate_gtfs_feed"
        },
       
)
async def validate(
    file: Optional[UploadFile] = File(None),
    url: Optional[str] = Form(None),
    format: str = Query("json", enum=["json", "html", "errors"], description="Response format: 'json' (default), 'html', or 'errors'"),
    api_key: str = Security(api_key_header_scheme)
):
    if isinstance(file, str) and file == "":
        file = None
    if not file and not url:
        raise HTTPException(400, "You must provide either a file or a URL.")
    if file and url:
        raise HTTPException(400, "Provide only one of file or URL, not both.")

    with tempfile.TemporaryDirectory() as work:
        feed = os.path.join(work, "feed.zip")
        if file:
            await save_uploaded_file(file, feed)
        else:
            await download_file(url, feed)
        run_validator(feed, work)
        return get_report(work, format)

# --- Overriding openapi() method to customize the schema ---
def custom_openapi():
    if app.openapi_schema:
        return app.openapi_schema

    openapi_schema = get_openapi(
        title=app.title,
        version=app.version,
        description=app.description,
        routes=app.routes,
    )

    # Ensure components and securitySchemes exist
    if "components" not in openapi_schema:
        openapi_schema["components"] = {}
        openapi_schema["components"]["securitySchemes"] = openapi_schema["components"].get("securitySchemes", {})

    openapi_schema["components"]["securitySchemes"]["ApiKeyAuth"] = GLOBAL_SECURITY_SCHEME
    
    openapi_schema["x-google-management"] = {
        "metrics": X_GOOGLE_MANAGEMENT_METRICS,
        "quota": X_GOOGLE_QUOTAS
    }

    app.openapi_schema = openapi_schema
    return app.openapi_schema

app.openapi = custom_openapi