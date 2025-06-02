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

---

## 1. Project Setup

1. **Clone the repository**
2. **Create a `.env` file** with your Google Cloud project info:
   
   ```env
   GCLOUD_PROJECT_ID=your-gcp-project-id
   GCLOUD_PROJECT_NUMBER=your-gcp-project-number
   ```

3. **Install required services and set up Google Cloud resources:**
   
   ```sh
   make cloud-setup
   ```

   This will enable all required Google Cloud services, set up Artifact Registry, and configure IAM roles.

---

## 2. Local Development & Testing

### a. Local Virtual Environment (hot-reload, fast iteration)

```sh
make venv         # creates .venv and installs dependencies
make dev          # runs FastAPI with hot-reload at http://localhost:8080
```

### b. Run Tests

```sh
make test         # runs all unit tests in tests/
```

### c. Lint and Type Check
```sh
make lint         # runs Ruff and mypy
```

---

## 3. Local Deployment (Docker)

Build and run the API in a container:

```sh
make docker-build      # builds the Docker image
make docker-run        # runs the API at http://localhost:8080 in Docker
```

## 4. Deploy to Google Cloud

```sh
make release
```
