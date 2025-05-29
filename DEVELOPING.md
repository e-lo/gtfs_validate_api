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

---

## 4. Deploy to Google Cloud

### a. Build and Push Image with Cloud Build
```sh
make gcloud-build
```

### b. Deploy to Cloud Run
```sh
make deploy-service
```

### c. Set Up API Gateway and Secure Cloud Run
```sh
make gateway-setup      # creates/updates API Gateway and config
make secure-cloud-run   # restricts Cloud Run ingress to API Gateway
```

### d. Full Release (all steps above)
```sh
make release
```

---

## 5. API Key Creation & Management

### a. Create an API Key (restricted to your API)
```sh
make key-create
```

### b. List API Keys
```sh
make key-list
```

You can also manage API keys in the Google Cloud Console under **APIs & Services > Credentials**.

---

## 6. Fetch and Update OpenAPI Spec

To fetch the OpenAPI spec from your deployed Cloud Run service and save as `openapi.yaml`:
```sh
make fetch-openapi-spec
```

---

## 7. Clean Up

To remove local virtual environment and clean up Docker images:
```sh
make clean
```

---

For more details on each Makefile target, run:
```sh
make help
```

```sh
make docker-build      # builds the Docker image
make docker-run        # runs the API at http://localhost:8080 in Docker
```

## Deploy to Google Cloud Run

```sh
docker push us-central1-docker.pkg.dev/gtfs-validator-api/validator/gtfs-validator:latest
```

```sh
make docker-deploy   # → Cloud Build → Artifact Registry → Cloud Run
```

## API-key security & quotas

```sh
make gateway-create   # once
make key-create       # per client
```

### Create a key restricted to your API

```bash
gcloud services api-keys create --display-name="editor-ui" \
       --api-targets=gtfs-validator-api=ALL
```

#### List keys to retrieve the value

```bash
gcloud services api-keys list --filter="displayName:editor-ui" \
       --format="value(keyString)"
```

## Docker Build Configuration

You can customize the Java version, GTFS Validator version, and JAR URL when building the Docker image:

```sh
docker build \
  --build-arg JAVA_VERSION=17-jre \
  --build-arg GTFS_VALIDATOR_VERSION=7.1.0 \
  --build-arg GTFS_VALIDATOR_JAR_URL=https://github.com/MobilityData/gtfs-validator/releases/download/v7.1.0/gtfs-validator-7.1.0-cli.jar \
  -t your-image-name .
```

If you use `make docker-build`, you can override these variables like this:

```sh
make docker-build JAVA_VERSION=17-jre GTFS_VALIDATOR_VERSION=7.1.0
```