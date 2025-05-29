# Development Notes

> **Prerequisite:**
> 
> To use Docker-based development and testing, you must have [Docker Desktop](https://www.docker.com/products/docker-desktop/) installed and running on your system (available for Mac, Windows, and Linux). After installation, verify Docker is available by running `docker --version` in your terminal.
>
> **Note:** The Docker build now downloads the GTFS Validator JAR from GitHub and supports configurable Java and validator versions via build arguments.

## Organization

```sh
.
├─ app/                # FastAPI entry-point (main.py)
├─ tests/              # Unit + smoke tests
├─ Dockerfile          # Two-stage Java→Python build
├─ openapi.yaml        # Gateway-configurable spec
├─ cloudbuild.yaml     # Automated build & push
└─ docs/               # Deployment & quota guides
```

## Setup Google Cloud

### Install CLIs

1. `jq`: `brew install jq`
2. [gcloud cli](https://cloud.google.com/sdk/docs/install)

### Create an .env folder and load following variables

```".env"
GCLOUD_PROJECT_ID=gtfs-validator-api
GCLOUD_PROJECT_NUMBER='12345678'
```

### Enable the services you will need and create the artifacts

```bash
make cloud-setup
```

## Local development

Build and run the API in a container, using the Makefile logic:

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