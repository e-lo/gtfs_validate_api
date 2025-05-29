# GTFS Validator Micro-service 🚦

> **Prerequisite:**
> 
> To use Docker-based development and testing, you must have [Docker Desktop](https://www.docker.com/products/docker-desktop/) installed and running on your system (available for Mac, Windows, and Linux). After installation, verify Docker is available by running `docker --version` in your terminal.
>
> **Note:** The Docker build now downloads the GTFS Validator JAR from GitHub and supports configurable Java and validator versions via build arguments.

A lightweight, stateless API that wraps the official **[MobilityData GTFS Validator](https://github.com/MobilityData/gtfs-validator)** and exposes it as a single `/validate` endpoint.  
Upload a GTFS `.zip` or provide a URL, receive a validation report in your chosen format.

| Feature | Notes |
|---------|-------|
| **Serverless-ready** | Designed for Google Cloud Run (default) but runs anywhere Docker does—including Fly.io, Render, Railway or locally. |
| **Fast cold-starts** | One-shot Java CLI lives in a slim image; typical cold-start ≤ 3 s, per-feed runtime ~50–120 s for 2 GB Bay-Area-sized feeds. |
| **Zero persistence** | No database—perfect for pay-per-request pricing and sandbox use. |
| **API-key & quota support** | Uses Google **API Gateway** for key issuance, per-key rate limits, and usage analytics. |
| **Language binding** | Pure REST (OpenAPI 3.0 spec included) → generate clients for Python, JS/TS, Go, etc. |
| **Cost @ 100 feeds/day** | Fits inside Cloud Run's free tier (~$0) or ≈ $1 on Fly.io (scale-to-zero). |

---

## Quickstart

### 1. Local Development

```sh
make venv         # create .venv and install dependencies
make dev          # run FastAPI with hot-reload at http://localhost:8080
```

### 2. Local Docker Usage

```sh
make docker-build      # builds the Docker image
make docker-run        # runs the API at http://localhost:8080 in Docker
```

### 3. Run Tests

```sh
make test
```

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

## Usage Examples

### Local (no API key required)

#### Validate a local GTFS file (default JSON response)

```sh
curl -X POST \
  -F "file=@feed.zip" \
  http://localhost:8080/validate
```

#### Validate a GTFS file from a URL

```sh
curl -X POST \
  -F "url=https://download.mobilitydata.org/gtfs/mdb/gtfs-2245.zip" \
  http://localhost:8080/validate
```

### Cloud (API Gateway, API key required)

#### Validate a local GTFS file (with API key)

```sh
curl -X POST \
  -F "file=@feed.zip" \
  -H "x-api-key: YOUR_API_KEY" \
  https://YOUR-GATEWAY-URL/validate
```

#### Validate a GTFS file from a URL (with API key)

```sh
curl -X POST \
  -F "url=https://download.mobilitydata.org/gtfs/mdb/gtfs-2245.zip" \
  -H "x-api-key: YOUR_API_KEY" \
  https://YOUR-GATEWAY-URL/validate
```

---

## Programmatic Usage

### Python Example

```python
import requests

api_url = "https://YOUR-GATEWAY-URL/validate"
api_key = "YOUR_API_KEY"

with open("feed.zip", "rb") as f:
    response = requests.post(
        api_url,
        files={"file": ("feed.zip", f, "application/zip")},
        headers={"x-api-key": api_key}
    )
print(response.status_code)
print(response.json())
```

### JavaScript Example (Node.js, using axios)

```js
const axios = require('axios');
const fs = require('fs');
const FormData = require('form-data');

const apiUrl = 'https://YOUR-GATEWAY-URL/validate';
const apiKey = 'YOUR_API_KEY';

const form = new FormData();
form.append('file', fs.createReadStream('feed.zip'));

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
