# Development Guide

> **Prerequisite:**
> - [Docker Desktop](https://www.docker.com/products/docker-desktop/) (for container-based workflows)
> - [gcloud CLI](https://cloud.google.com/sdk/docs/install) (for Google Cloud deployment)
> - [jq](https://stedolan.github.io/jq/) (for some scripts)

---

## Project Structure

```
.
├─ app/                # FastAPI entry-point (main.py)
├─ tests/              # Unit + smoke tests
├─ Dockerfile          # Two-stage Java→Python build
├─ openapi.yaml        # Gateway-configurable spec
├─ cloudbuild.yaml     # Automated build & push
└─ docs/               # Deployment & quota guides
```

## Local Development

```sh
make dev-env         # creates .venv and installs dependencies
make docker-build           # builds the Docker image
make docker-run-dev         # runs the API at http://localhost:8080 in Docker
```

### Lint + Test

```sh
make lint         # runs Ruff and mypy
make test         # runs all unit tests in tests/
```

## Google Cloud Deployment

### Instantiate required g-cloud services

```sh
make gcloud-setup
```

### Add required production environment variables to production environment

```sh
BASE_URL
DISABLE_EMAIL_AND_API_KEY #False
APP_ENV #production
GCLOUD_PROJECT_ID
GCLOUD_PROJECT_NUMBER
MAIL_USERNAME #from mailjet
MAIL_PASSWORD #from mailjet
MAIL_FROM 
MAIL_PORT #537
MAIL_SERVER #from mailjet
MAIL_STARTTLS #True
MAIL_SSL_TLS #False
RATE_LIMIT_UNAUTH_LIMIT
RATE_LIMIT_AUTH_LIMIT
```

## Deploy to Google Cloud

```sh
make gcloud-deploy
```
