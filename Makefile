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
PROJECT_NUMBER   ?= $(shell gcloud projects describe $(PROJECT) --format='value(projectNumber)')
PROJECT          := $(shell gcloud config get-value project)
REGION           := us-central1
SERVICE          := gtfs-validator
REPO             := $(REGION)-docker.pkg.dev/$(PROJECT)/validator
IMAGE_TAG        := $(REPO)/$(SERVICE):$(SHORT_SHA)
LATEST_IMAGE_TAG := $(REPO)/$(SERVICE):latest
SHORT_SHA        := $(shell git rev-parse --short HEAD)

# API Gateway specific variables
API_ID                 := gtfs-validator-api
API_CONFIG_ID          := gtfs-config-$(SHORT_SHA)
LATEST_API_CONFIG_ID   := gtfs-config-latest
GATEWAY_ID             := gtfs-validator-gateway
# Name for the SA API Gateway will use
GW_SERVICE_ACCOUNT     := $(SERVICE)-gw-invoker
GW_SA_EMAIL            := $(GW_SERVICE_ACCOUNT)@$(PROJECT).iam.gserviceaccount.com
CLOUD_RUN_SERVICE_URL  := $(shell gcloud run services describe $(SERVICE) --platform managed --region $(REGION) --format='value(status.url)' 2>/dev/null)
OPENAPI_FILE           := openapi.yaml

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

# -------------- Development --------------------------------------------------
venv: ## Create local virtualenv via uv
	@echo "🔧 Creating local virtualenv (.venv) with uv"
	@echo "[INFO] For Docker-based workflows, ensure Docker Desktop is installed and running."
	uv venv .venv
	. .venv/bin/activate && uv pip install ".[dev]"
	@touch .venv/bin/activate

dev: venv ## Run the API locally on http://localhost:8080
	@echo "🚀 Starting FastAPI with hot-reload"
	. .venv/bin/activate && uvicorn app.main:app --reload --host 0.0.0.0 --port 8080

test: venv ## Run unit tests
	. .venv/bin/activate && pytest -q

lint: venv ## Run Ruff and mypy
	. .venv/bin/activate && ruff check app && mypy app

# -------------- Container build ---------------------------------------------
docker-build: check-docker ## Build the Docker image locally
	docker build --platform=linux/amd64 -t $(IMAGE_TAG) .

docker-run: docker-build ## Run the container locally
	@if lsof -i :8080 >/dev/null 2>&1; then \
	  echo "[ERROR] Port 8080 is already in use."; \
	  echo "To find the process using it, run: lsof -i :8080"; \
	  echo "To kill the process, run: kill <PID> (replace <PID> with the number from the previous command)"; \
	  exit 1; \
	fi
	docker run --rm -p 8080:8080 $(IMAGE_TAG)

# -------------- Cloud Setup -------------------------------------------------
cloud-setup: ## Grant required IAM roles and set up services
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
						apikeys.googleapis.com # Added iam for SA creation
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
	@echo "Service Account Setup for API Gateway Invoker"
	@echo "-----------------------------------------------------------------------"
	@echo "Project ID being used: $(PROJECT)"
	@echo "Service Account Name: $(GW_SERVICE_ACCOUNT)"
	@echo "Expected Service Account Email: $(GW_SA_EMAIL)"
	@echo "Checking if Service Account $(GW_SA_EMAIL) exists in project $(PROJECT)..."
	@-gcloud iam service-accounts describe "$(GW_SA_EMAIL)" --project="$(PROJECT)" >/dev/null 2>&1; \
	SA_EXISTS_EC=$$?; \
	echo "Exit code of describe command: $$SA_EXISTS_EC"; \
	if [ $$SA_EXISTS_EC -ne 0 ]; then \
		echo "Service Account $(GW_SA_EMAIL) does not appear to exist (describe failed with exit code $$SA_EXISTS_EC). Attempting to create it..."; \
		gcloud iam service-accounts create "$(GW_SERVICE_ACCOUNT)" \
			--display-name="API Gateway Invoker for $(SERVICE) service" \
			--description="Service account for API Gateway to invoke the $(SERVICE) Cloud Run service" \
			--project="$(PROJECT)"; \
		if [ $$? -eq 0 ]; then \
		    echo "Service Account $(GW_SA_EMAIL) created successfully."; \
		    echo "Waiting 10 seconds for propagation before IAM binding..."; \
		    sleep 10; \
		else \
		    echo "Service Account creation failed. Please check errors above."; \
		    exit 1; \
		fi; \
	else \
		echo "Service Account $(GW_SA_EMAIL) already exists (describe succeeded with exit code $$SA_EXISTS_EC)."; \
	fi
	@echo "Service Account setup check complete."
	@echo "#######################################################################"

	@echo "-----------------------------------------------------------------------"
	@echo "Granting Cloud Run Invoker role to $(GW_SA_EMAIL) for service $(SERVICE)..."
	@echo "-----------------------------------------------------------------------"
	gcloud run services add-iam-policy-binding "$(SERVICE)" \
		--member="serviceAccount:$(GW_SA_EMAIL)" \
		--role="roles/run.invoker" \
		--region="$(REGION)" \
		--platform=managed \
		--project="$(PROJECT)" \
		--quiet
	@echo "Cloud Run Invoker role granted."
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

deploy-service: gcloud-build ## Deploy to Cloud Run, tag :latest
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

fetch-openapi-spec: ## Fetch openapi.json from deployed Cloud Run service and save as openapi.yaml
	@echo "Fetching OpenAPI spec from $(CLOUD_RUN_SERVICE_URL)/openapi.json"
	@if [ -z "$(CLOUD_RUN_SERVICE_URL)" ]; then \
		echo "[ERROR] Cloud Run service URL for '$(SERVICE)' not found. Has it been deployed?"; \
		exit 1; \
	fi
	@curl -sfL "$(CLOUD_RUN_SERVICE_URL)/openapi.json" -o $(OPENAPI_FILE) || \
		(echo "[ERROR] Failed to fetch openapi.json. Check if the service is running and /openapi.json is accessible." && exit 1)
	@echo "OpenAPI spec saved to $(OPENAPI_FILE)"

# -------------- API Gateway & keys ------------------------------------------
gateway-setup: fetch-openapi-spec ## Create/Update API, API Config, and Gateway
	@echo "Setting up API Gateway..."
	@if ! gcloud api-gateway apis describe $(API_ID) --project=$(PROJECT) >/dev/null 2>&1; then \
		echo "Creating API Gateway API: $(API_ID)..."; \
		gcloud api-gateway apis create $(API_ID) --project=$(PROJECT); \
	else \
		echo "API Gateway API '$(API_ID)' already exists."; \
	fi
	@echo "Creating/Updating API Config: $(API_CONFIG_ID) for API $(API_ID)..."
	gcloud api-gateway api-configs create $(API_CONFIG_ID) \
		--api=$(API_ID) \
		--openapi-spec=$(OPENAPI_FILE) \
		--project=$(PROJECT) \
		--display-name="Config $(SHORT_SHA)"

	@if ! gcloud api-gateway gateways describe $(GATEWAY_ID) --location=$(REGION) --project=$(PROJECT) >/dev/null 2>&1; then \
		echo "Creating API Gateway: $(GATEWAY_ID)..."; \
		gcloud api-gateway gateways create $(GATEWAY_ID) \
			--api=$(API_ID) \
			--api-config=$(API_CONFIG_ID) \
			--location=$(REGION) \
			--project=$(PROJECT); \
	else \
		echo "Updating API Gateway $(GATEWAY_ID) to use config $(API_CONFIG_ID)..."; \
		gcloud api-gateway gateways update $(GATEWAY_ID) \
			--api=$(API_ID) \
			--api-config=$(API_CONFIG_ID) \
			--location=$(REGION) \
			--project=$(PROJECT); \
	fi
	@echo "API Gateway URL: https://$(shell gcloud api-gateway gateways describe $(GATEWAY_ID) --location=$(REGION) --project=$(PROJECT) --format='value(defaultHostname)')"

secure-cloud-run: ## Restrict Cloud Run ingress to internal and API Gateway traffic
	@echo "Securing Cloud Run service $(SERVICE) by restricting ingress..."
	gcloud run services update $(SERVICE) \
		--ingress=internal-and-cloud-load-balancing \
		--region=$(REGION) \
		--platform=managed \
		--project=$(PROJECT) \
		--quiet
	@echo "Cloud Run service ingress updated."

key-create: ## Issue an API key named "gtfs-validator-key" restricted to this API
	@echo "Creating API key 'gtfs-validator-key' for API $(API_ID)..."
	@API_KEY_STRING=$$(gcloud services api-keys create --display-name="gtfs-validator-key" --project=$(PROJECT) --format="value(keyString)"); \
	echo "API Key created. Waiting a few seconds for propagation before restricting..."; \
	sleep 10; \
	gcloud services api-keys add-iam-policy-binding $$API_KEY_STRING \
	    --member="service:$(API_ID).apigateway.$(PROJECT).cloud.goog" \
	    --role="roles/apigateway.apiKeyUser" \
	    --project=$(PROJECT)
    # For API Gateway, you usually restrict keys by enabling the API Gateway's managed service on the key.
	@echo "Key 'gtfs-validator-key' created: $$API_KEY_STRING"

key-list: ## Show all API keys
	gcloud services api-keys list --project=$(PROJECT) --format="table(displayName, keyString, createTime)"

# -------------- Full Deployment Orchestration --------------------------------
release: deploy-service gateway-setup secure-cloud-run ## Deploy service, setup gateway, and secure Cloud Run
	@echo "✅ Full release process complete!"
	@echo "API Gateway URL: https://$(shell gcloud api-gateway gateways describe $(GATEWAY_ID) --location=$(REGION) --project=$(PROJECT) --format='value(defaultHostname)')"
	@echo "Remember to create and restrict API keys as needed using 'make key-create' or the console."


# -------------- Clean --------------------------------------------------------
clean: ## Remove local venv & dangling Docker images
	@rm -rf .venv
	-docker image prune -f

.DEFAULT_GOAL := help

