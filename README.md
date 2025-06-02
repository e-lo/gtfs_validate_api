# GTFS Validator Micro-service 🚦

> **Prerequisite:**
> 
> Docker build now downloads the GTFS Validator JAR.  To use and test locally, you must have [Docker Desktop](https://www.docker.com/products/docker-desktop/) installed and running on your system (available for Mac, Windows, and Linux). After installation, verify Docker is available by running `docker --version` in your terminal.
>

A lightweight, stateless API that wraps the official **[MobilityData GTFS Validator](https://github.com/MobilityData/gtfs-validator)** and exposes it as a single `/validate` endpoint.  

Upload a GTFS `.zip` or provide a URL, receive a validation report in your chosen format.

| Feature | Notes |
|---------|-------|
| **Serverless-ready** | Designed for Google Cloud Run (default) but can run wherever Docker can. |
| **Fast cold-starts** | One-shot Java CLI lives in a slim image; typical cold-start ≤ 3 s. |
| **Zero persistence** | No database to manage (other than API keys...and those are optional). |
| **API-key & quota support** | Optionally uses Firestore to manage users and API keys in order to impose rates based on keys. |
| **User registration & verification** | Auto-issues API keys to emails which are verified.  Currently leverages Mailjet's free usage tier to send verification emails. |
| **Language binding** | Pure REST (OpenAPI 3.0 spec included) → generate clients for Python, JS/TS, Go, etc. |
| **Cost @ 100 feeds/day** | Currently fits well inside Cloud Run's free tier. |

---

## Quickstart

1. **Create the virtual environment and install dependencies:**

   ```sh
   make venv
   ```

2. **Run FastAPI locally (no user authentication):**

   ```sh
   make docker-run-localprod
   # App will be available at http://localhost:8080
   ```

---

## Environment Variables

The application uses the following environment variables for configuration. You can use `.env.local`, `.env.development`, or `.env.production` files depending on your environment. **Never commit real secrets to version control.**

| Name           | Description                        | Example/Notes                |
|----------------|------------------------------------|------------------------------|
| BASE_URL       | Public URL of your app             | https://yourdomain.com       |
| MAIL_USERNAME  | SMTP/API username                  | Mailjet API key              |
| MAIL_PASSWORD  | SMTP/API password/secret           | Mailjet secret key           |
| MAIL_FROM      | Verified sender email              | noreply@yourdomain.com       |
| MAIL_PORT      | SMTP port                          | 587                          |
| MAIL_SERVER    | SMTP server host                   | in-v3.mailjet.com            |
| MAIL_STARTTLS  | Use STARTTLS for SMTP              | True                         |
| MAIL_SSL_TLS   | Use SSL/TLS for SMTP               | False                        |
| APP_ENV        | (optional) Set to 'production', 'development', or 'local' to select config | production                   |
| DISABLE_EMAIL_AND_API_KEY | (optional) If True, bypasses all email and API key checks (for local prod/testing) | True/False |

---

## Environment Summary Table

| Environment         | .env file         | Email/API Key Required? | Notes                        |
|---------------------|-------------------|------------------------|------------------------------|
| Local dev/testing   | .env.development  | No                     | Dummy or test SMTP           |
| Local production    | .env.local        | No (set DISABLE_EMAIL_AND_API_KEY=True) | Bypasses email/API key checks |
| Cloud production    | .env.production   | Yes                    | Use real secrets             |

> For local production/testing, set `DISABLE_EMAIL_AND_API_KEY=True` in your `.env` to bypass email verification and API key checks.

---

## Using a Specific Version of the GTFS Validator

You can build the service with any official release of the MobilityData GTFS Validator by specifying the version and JAR URL at build time.

### Example: Use GTFS Validator v7.1.0

#### With Docker directly

```sh
docker build \
  --build-arg JAVA_VERSION=17-jre \
  --build-arg GTFS_VALIDATOR_VERSION=7.1.0 \
  --build-arg GTFS_VALIDATOR_JAR_URL=https://github.com/MobilityData/gtfs-validator/releases/download/v7.1.0/gtfs-validator-7.1.0-cli.jar \
  -t gtfs-validator:7.1.0 .
```

#### With Makefile

```sh
make docker-build GTFS_VALIDATOR_VERSION=7.1.0 \
  GTFS_VALIDATOR_JAR_URL=https://github.com/MobilityData/gtfs-validator/releases/download/v7.1.0/gtfs-validator-7.1.0-cli.jar
```

You can find the latest releases and their JAR URLs at:
https://github.com/MobilityData/gtfs-validator/releases

---

## Endpoint Reference

| Method | Path        | Body                                               | Query Params | Response                                                                                                     |
| ------ | ----------- | -------------------------------------------------- | ------------ | ------------------------------------------------------------------------------------------------------------ |
| `POST` | `/validate` | `multipart/form-data` field **file** (GTFS `.zip`) _or_ **url** (GTFS `.zip` URL) | `format` (optional: `json` (default), `html`, `errors`) | `200 OK` JSON, HTML, or errors-only JSON report. <br>`400` if neither or both file and url are provided.<br>`500` if validator fails. |

### Parameters

- **file**: (optional) GTFS `.zip` file upload. Use this for local files.
- **url**: (optional) URL to a GTFS `.zip` file. Use this to validate a remote file.
- **format**: (optional, query) One of:
  - `json` (default): Full JSON validation report.
  - `html`: HTML validation report (as `text/html`).
  - `errors`: Only errors (notices with severity `ERROR`) as JSON.

**Note:** You must provide either `file` or `url`, but not both.

---

## Usage

### Command Line

Validate `gtfsfeed.zip`

```sh
curl -X POST \
  -F "file=@gtfsfeed.zip" \
  https://<YOUR-GATEWAY-URL>/validate
```

Use your API key in the header to increase your rate limits:

```sh
curl -X POST \
  -F "file=@feed.zip" \
  -H "x-api-key: <YOUR_API_KEY>" \
  https://<YOUR-GATEWAY-URL>/validate
```

Validate a feed hosted remotely at mobilitydata.org:

```sh
curl -X POST \
  -F "url=https://download.mobilitydata.org/gtfs/mdb/gtfs-2245.zip" \
  -H "x-api-key: <YOUR_API_KEY>" \
  https://<YOUR-GATEWAY-URL>/validate
```

Validate a feed and get returned the HTML report:

```sh
curl -X POST \
  -F "url=https://download.mobilitydata.org/gtfs/mdb/gtfs-2245.zip" \
  -H "x-api-key: <YOUR_API_KEY>" \
  "https://<YOUR-GATEWAY-URL>/validate?format=html"
```

### Python

```python
import requests

api_url = "https://<YOUR-GATEWAY-URL>/validate"
api_key = "<YOUR_API_KEY>"
gtfs_zipfile = "gtfsfeed.zip"

with open(gtfs_zipfile, "rb") as f:
    response = requests.post(
        api_url,
        params={"format": "html"}, # <--- Optional. can be json (default), html or errors (which is also json)
        files={"file": (gtfs_zipfile, f, "application/zip")}, # use this to validate a local feed
        # url = "https://download.mobilitydata.org/gtfs/mdb/gtfs-2245.zip", # use this if you want to validate a feed at a URL
        headers={"x-api-key": api_key}
    )
print(response.status_code)
print(response.json())
```

### JavaScript (Node.js, using axios)

```js
const axios = require('axios');
const fs = require('fs');
const FormData = require('form-data');

const apiUrl = 'https://<YOUR-GATEWAY-URL>/validate';
const apiKey = '<YOUR_API_KEY>';

const form = new FormData();
form.append('file', fs.createReadStream('gtfsfeed.zip'));

axios.post(apiUrl, form, {
  headers: {
    ...form.getHeaders(),
    'x-api-key': apiKey
  }
})
.then(res => {
  console.log(res.data);
})
.catch(err => {
  console.error(err.response ? err.response.data : err);
});
```

---

## OpenAPI Spec

See full schema in `openapi.yaml` (auto-generated or fetched from the deployed service).

---

## License

MIT License

## Administrative Endpoints

### Delete User (Admin)

**Endpoint:** `POST /admin/delete-user`

Deletes a user from Firestore by email. In production, access is controlled by Firestore authentication and IAM permissions. In the emulator, all requests are allowed.

**Request fields:**
- `email` (form field, required): The email address of the user to delete.

**Example usage with curl:**

```
curl -X POST -F "email=user@example.com" http://localhost:8080/admin/delete-user
```

**Note:**
- In production, only callers with valid Firestore credentials and permissions can use this endpoint.
- In the emulator, any client can call this endpoint.

## Rate Limiting

- **Authenticated users (with API key):** Higher rate limits (default: 50/day, configurable via environment).
- **Unauthenticated users:** Lower rate limits (default: 5/day, configurable via environment).
- **Disabling Rate Limiting:** If `DISABLE_EMAIL_AND_API_KEY=True` in your environment, all rate limiting and API key checks are disabled for local development/testing.

The rate limit is determined dynamically per request. See the `RateLimitSettings` in your environment variables for configuration.

> **Note:** The `/validate` endpoint enforces different rate limits for requests with and without an API key. If you exceed your quota, you'll receive a `429 Too Many Requests` error.

---

## Environment Variables (Rate Limiting)

| Name                | Description                        | Example/Notes                |
|---------------------|------------------------------------|------------------------------|
| AUTH_LIMIT          | Rate limit for authenticated users | 50/day                       |
| UNAUTH_LIMIT        | Rate limit for unauthenticated     | 5/day                        |

---

## OpenAPI/Swagger UI

The OpenAPI docs at `/docs` always reflect the current environment and rate limiting logic.

---

## Testing and Local Development

All tests pass and the dynamic rate limiting logic is covered by the test suite. You can run tests with:

```sh
pytest --maxfail=5 --disable-warnings -v
```

---

## Advanced: Dynamic Rate Limiting Implementation

This project uses a dynamic rate limiting approach based on user authentication, as discussed in [slowapi issue #13](https://github.com/laurentS/slowapi/issues/13). The rate limit is determined per request using a lambda and an optional request argument.
