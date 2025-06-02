# GTFS Validator Micro-service 🚌

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

## Local Quickstart

Install prerequisites:

- [Docker Desktop](https://www.docker.com/)
- [uv](https://docs.astral.sh/uv/getting-started/installation/)
- [make](https://www.gnu.org/software/make/manual/make.html) , e.g. `apt-get -y install make` or `brew install make`

Setup and run:

   ```sh
   make venv #Create the virtual environment and install dependencies
   make docker-run-local # Run FastAPI locally (no user authentication)
   ```

View local instance at `https://localhost:8080` and access OpenAPI docs at: `https://localhost:8080/docs`

Validate `gtfsfeed.zip` and return HTML report:

```sh
curl -X POST \
  -F "file=@gtfsfeed.zip" \
  "https://localhost:8080/validate?format=html"
```

Validate a feed at a URL and get json response from the validator:

```sh
curl -X POST \
  -F "url=https://download.mobilitydata.org/gtfs/mdb/gtfs-2245.zip" \
  https://localhost:8080/validate
```

## Endpoint Reference

Full documentation of endpoints is at <<YOUR-GATEWAY-URL>/docs>

Note: you can also use the API directly from the docs by clicking "try out".

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

## Deployed Usage

### Command Line

Validate `gtfsfeed.zip`

```sh
curl -X POST \
  -F "file=@gtfsfeed.zip" \
  <YOUR-GATEWAY-URL>/validate
```

Use your API key in the header to increase your rate limits:

```sh
curl -X POST \
  -F "file=@feed.zip" \
  -H "x-api-key: <YOUR_API_KEY>" \
  <YOUR-GATEWAY-URL>/validate
```

Validate a feed hosted remotely at mobilitydata.org:

```sh
curl -X POST \
  -F "url=https://download.mobilitydata.org/gtfs/mdb/gtfs-2245.zip" \
  -H "x-api-key: <YOUR_API_KEY>" \
  <YOUR-GATEWAY-URL>/validate
```

Validate a feed and get returned the HTML report:

```sh
curl -X POST \
  -F "url=https://download.mobilitydata.org/gtfs/mdb/gtfs-2245.zip" \
  -H "x-api-key: <YOUR_API_KEY>" \
  "<YOUR-GATEWAY-URL>/validate?format=html"
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

## Licenses

- Microservice: MIT
- GTFS Validator: Apache See [LICENSE](https://github.com/MobilityData/gtfs-validator/blob/master/LICENSE)

## Administrative Endpoints

### Delete User (Admin)

**Endpoint:** `POST /admin/delete-user`

Deletes a user from Firestore by email. In production, access is controlled by Firestore authentication and IAM permissions. In the emulator, all requests are allowed.

**Request fields:**

- `email` (form field, required): The email address of the user to delete.

**Example usage with curl:**

```sh
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

Rate limits are set by the following environment variables

| Name                | Description                        | Example/Notes                |
|---------------------|------------------------------------|------------------------------|
| DISABLE_EMAIL_AND_API_KEY | Enables or disables rate limiting | True / False |
| AUTH_LIMIT          | Rate limit for authenticated users | 50/day                       |
| UNAUTH_LIMIT        | Rate limit for unauthenticated     | 5/day                        |

---

## OpenAPI/Swagger UI

The OpenAPI docs at `/docs` always reflect the current environment and rate limiting logic.

## Environment Summary Table

| Environment         | .env file         | Email/API Key Required? | Notes                        |
|---------------------|-------------------|------------------------|------------------------------|
| Local dev/testing   | .env.development  | No                     | Dummy or test SMTP           |
| Local production    | .env.local        | No (set DISABLE_EMAIL_AND_API_KEY=True) | Bypasses email/API key checks |
| Cloud production    | .env.production   | Yes                    | Use real secrets             |

### Environment Variables

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

## Local Development Instructions

See <DEVELOPING.md>
