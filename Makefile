#───────────────────────────────────────────────────────────────
# GTFS-Validator – one-command dev, build, deploy
#
# Each target is documented; run `make` or `make help`.
#
# Conventions
# • All Python tasks run inside a local .venv created by uv.
# • GCP project is read from `gcloud config get-value project`.
#───────────────────────────────────────────────────────────────

# -------------- Environment --------------------------------------------------
ifneq (,$(wildcard .env))
  include .env
  export
endif

# -------------- Variables ----------------------------------------------------
PROJECT          := $(shell gcloud config get-value project)
PROJECT_NUMBER   ?= $(shell gcloud projects describe $(PROJECT) --format='value(projectNumber)')
REGION           := us-central1
SERVICE          := gtfs-validator
SHORT_SHA        := $(shell git rev-parse --short HEAD 2>/dev/null || echo dev)
REPO             := $(REGION)-docker.pkg.dev/$(PROJECT)/validator
IMAGE_TAG        := $(REPO)/$(SERVICE):$(SHORT_SHA)
LATEST_IMAGE_TAG := $(REPO)/$(SERVICE):latest
# Set your Firestore emulator project ID here
FIRESTORE_PROJECT_ID 	:= firestore-emulator-example
FIRESTORE_EMULATOR_PORT := 8080

# -------------- Helper -------------------------------------------------------
.PHONY: help check-docker
help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) | \
	sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-25s\033[0m %s\n", $$1, $$2}'

check-docker:
	@command -v docker >/dev/null 2>&1 || ( \
		echo >&2 "Docker is not installed! Please install Docker Desktop: https://www.docker.com/products/docker-desktop/"; \
		exit 1 )
	@docker info >/dev/null 2>&1 || ( \
		echo >&2 "Docker is not running! Please start Docker Desktop before continuing."; \
		exit 1 )

# -------------- Local Environment Setup --------------------------------------------------

venv: ## Create local virtualenv via uv
	@echo "🔧 Creating local virtualenv (.venv) with uv"
	uv venv .venv
	. .venv/bin/activate && uv pip install .
	@touch .venv/bin/activate

dev-env: venv 
	@echo "Installing Firestore emulator..."
	uv pip install ".[dev]"
	gcloud components install beta --quiet || true
	gcloud components install cloud-firestore-emulator --quiet || true

cloud-env: venv 
	uv pip install ".[cloud]"

test: venv ## Run unit tests
	. .venv/bin/activate && pytest -q

lint: venv ## Run Ruff and mypy, and fix Markdown files if possible
	. .venv/bin/activate && ruff check --fix-only app && mypy app
	. .venv/bin/activate && ruff format
	@command -v markdownlint >/dev/null 2>&1 && markdownlint --fix '**/*.md' || npx --no-install markdownlint --fix '**/*.md' || echo "markdownlint not found. Skipping markdown lint."

# -------------- Container build ---------------------------------------------
docker-build: check-docker ## Build the Docker image locally
	docker build --platform=linux/amd64 -t $(IMAGE_TAG) .

docker-run-local: docker-build ## Run the container locally in local production mode (no API keys, no DB, no rate limiting)
	@if lsof -i :8080 >/dev/null 2>&1; then \
	  PID=$$(lsof -ti :8080); \
	  echo "[ERROR] Port 8080 is already in use by process $$PID."; \
	  read -p "Do you want to kill it and proceed? [y/N] " yn; \
	  case $$yn in \
	    [Yy]*) kill -9 $$PID; echo "Killed process $$PID.";; \
	    *) echo "Aborting."; exit 1;; \
	  esac; \
	fi
	@echo "Running API container in local production mode (no API keys, no DB, no rate limiting)"
	docker run --rm --env-file .env.local -p 8080:8080 $(IMAGE_TAG)

# For local dev/testing: uses .env.development and starts Firestore emulator
# Make sure .env.development contains FIRESTORE_EMULATOR_HOST=localhost:8081

docker-run-dev: docker-build ## Run the container locally with Firestore emulator and full API logic
	@if lsof -i :8080 >/dev/null 2>&1; then \
	  PID=$$(lsof -ti :8080); \
	  echo "[ERROR] Port 8080 is already in use by process $$PID."; \
	  read -p "Do you want to kill it and proceed? [y/N] " yn; \
	  case $$yn in \
	    [Yy]*) kill -9 $$PID; echo "Killed process $$PID.";; \
	    *) echo "Aborting."; exit 1;; \
	  esac; \
	fi
	@echo "Starting Firestore emulator in background..."
	gcloud beta emulators firestore start --host-port=127.0.0.1:8081 &
	@echo "Waiting for Firestore emulator to start..."
	sleep 3
	@echo "Running API container with .env.development (FIRESTORE_EMULATOR_HOST=--host-port=127.0.0.1:8081)"
	docker run --rm --env-file .env.development -p 8080:8080 $(IMAGE_TAG)

run-dev: ## Run the API
	@echo "🚀 Starting FastAPI with hot-reload"
	. .venv/bin/activate && uvicorn app.main:app --reload --host 0.0.0.0 --port 8080

run-prod:
	. .venv/bin/activate && uvicorn app.main:app --host 0.0.0.0 --port 8080

# -------------- Cloud Setup -------------------------------------------------
init-cloud-setup: ## Grant required IAM roles and set up services
	gcloud auth login
	@echo "Verifying/Setting project to $(PROJECT)..."
	@if ! gcloud projects describe $(PROJECT) >/dev/null 2>&1; then \
		echo "Project $(PROJECT) does not exist or you don't have permissions. Please create it or check permissions."; \
		exit 1; \
	fi
	gcloud config set project $(PROJECT)
	@echo "-----------------------------------------------------------------------"
	@echo "Enabling required services..."
	@echo "-----------------------------------------------------------------------"
	gcloud services enable run.googleapis.com \
						artifactregistry.googleapis.com \
						cloudbuild.googleapis.com \
						apigateway.googleapis.com \
						servicemanagement.googleapis.com \
						servicecontrol.googleapis.com \
						iam.googleapis.com \
						apikeys.googleapis.com \
						firestore.googleapis.com
	@echo "#######################################################################"

	@echo "-----------------------------------------------------------------------"
	@echo "Checking/Creating Artifact Registry repository..."
	@echo "-----------------------------------------------------------------------"
	@if ! gcloud artifacts repositories describe validator --location=$(REGION) --project=$(PROJECT) >/dev/null 2>&1; then \
		echo "Creating Artifact Registry repository 'validator' in $(REGION)..."; \
		gcloud artifacts repositories create validator \
			--repository-format=docker \
			--location=$(REGION) \
			--project=$(PROJECT) \
			--description="Docker repository for GTFS Validator"; \
	else \
		echo "Artifact Registry repository 'validator' already exists."; \
	fi
	@echo "Configuring Docker to use Artifact Registry..."
	gcloud auth configure-docker $(REGION)-docker.pkg.dev --project=$(PROJECT)
	@echo "Artifact Registry repository 'validator' created and configured successfully."
	@echo "#######################################################################"

	@echo "-----------------------------------------------------------------------"
	@echo "Granting roles to Cloud Build service account..."
	@echo "-----------------------------------------------------------------------"
	gcloud projects add-iam-policy-binding $(PROJECT) \
		--member="serviceAccount:$(PROJECT_NUMBER)@cloudbuild.gserviceaccount.com" \
		--role="roles/run.admin" --condition=None # For deploying to Cloud Run
	gcloud projects add-iam-policy-binding $(PROJECT) \
		--member="serviceAccount:$(PROJECT_NUMBER)@cloudbuild.gserviceaccount.com" \
		--role="roles/iam.serviceAccountUser" --condition=None # For acting as other SAs if needed
	gcloud projects add-iam-policy-binding $(PROJECT) \
		--member="serviceAccount:$(PROJECT_NUMBER)@cloudbuild.gserviceaccount.com" \
		--role="roles/artifactregistry.writer" --condition=None
	@echo "Cloud Build role granted."
	@echo "#######################################################################"

	@echo "Cloud setup tasks complete."
	@echo "#######################################################################"

# -------------- Cloud Build & Run -------------------------------------------

gcloud-build: cloudbuild.yaml ## Build & push image with Cloud Build → Artifact Registry
	@echo "Building image with SHORT_SHA: $(SHORT_SHA)"
	gcloud builds submit \
		--config cloudbuild.yaml \
		--project=$(PROJECT) \
		--substitutions _REPO=$(REPO),_SERVICE=$(SERVICE),_SHORT_SHA=$(SHORT_SHA)
		--build-arg APP_ENV=production

deploy-service: update-cloudrun-secrets gcloud-build ## Deploy to Cloud Run, tag :latest
	@echo "Deploying $(SERVICE) to Cloud Run from image $(REPO)/$(SERVICE):$(SHORT_SHA)"
	gcloud run deploy $(SERVICE) \
		--image=$(REPO)/$(SERVICE):$(SHORT_SHA) \
		--memory=2Gi --cpu=1 --timeout=600s --concurrency=1 \
		--max-instances=2 \
		--allow-unauthenticated \
		--region=$(REGION) \
		--platform=managed \
		--project=$(PROJECT) \
		--service-account=$(PROJECT_NUMBER)-compute@developer.gserviceaccount.com
	@echo "Tagging image $(REPO)/$(SERVICE):$(SHORT_SHA) as $(LATEST_IMAGE_TAG)"
	gcloud artifacts docker tags add $(REPO)/$(SERVICE):$(SHORT_SHA) $(LATEST_IMAGE_TAG) --project=$(PROJECT) --quiet
	@echo "Cloud Run service $(SERVICE) deployed. URL: $(shell gcloud run services describe $(SERVICE) --platform managed --region $(REGION) --project=$(PROJECT) --format='value(status.url)')"


# -------------- Full Deployment Orchestration --------------------------------
release: deploy-service
	@echo "✅ Full release process complete!"

# --- Google Cloud Secret Manager integration ---
# Usage:
#   make secrets-create         # Create or update secret from .env.production
#   make secrets-update         # Update secret value from .env.production
#   make update-cloudrun-secrets # Mount secrets as env vars in Cloud Run

SECRET_NAME ?= $(SERVICE)-env-production

secrets-create:
	@echo "Creating or updating secret $(SECRET_NAME) from .env.production..."
	@if gcloud secrets describe $(SECRET_NAME) --project=$(PROJECT) >/dev/null 2>&1; then \
		echo "Secret exists, updating..."; \
		gcloud secrets versions add $(SECRET_NAME) --data-file=.env.production --project=$(PROJECT); \
	else \
		echo "Secret does not exist, creating..."; \
		gcloud secrets create $(SECRET_NAME) --data-file=.env.production --replication-policy=automatic --project=$(PROJECT); \
	fi

secrets-update: secrets-create
	@echo "Secret $(SECRET_NAME) updated."

update-cloudrun-secrets:
	@echo "Mounting secrets as env vars in Cloud Run..."
	@# Extract variable names from .env.production
	VARS=$$(grep -v '^#' .env.production | grep '=' | cut -d= -f1 | xargs); \
	CMD="gcloud run services update $(SERVICE) --region=$(REGION) --platform=managed"; \
	for VAR in $$VARS; do \
		CMD="$$CMD --update-secrets $$VAR=$(SECRET_NAME):latest:$$VAR"; \
	done; \

.PHONY: start-firestore-emulator
start-firestore-emulator:
	@echo "Starting Firestore emulator on port $(FIRESTORE_EMULATOR_PORT)..."
	@gcloud beta emulators firestore start --host-port=127.0.0.1:$(FIRESTORE_EMULATOR_PORT) > /dev/null 2>&1 & \
	sleep 3

.PHONY: clear-firestore
clear-firestore: start-firestore-emulator
	@echo "Clearing Firestore emulator data..."
	@curl -s -X DELETE "http://localhost:$(FIRESTORE_EMULATOR_PORT)/emulator/v1/projects/$(FIRESTORE_PROJECT_ID)/databases/(default)/documents" && echo "Firestore emulator cleared."