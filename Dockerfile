# ---- Configurable build arguments ----
ARG JAVA_VERSION=17-jre
ARG GTFS_VALIDATOR_VERSION=7.1.0
ARG GTFS_VALIDATOR_JAR_URL=https://github.com/MobilityData/gtfs-validator/releases/download/v${GTFS_VALIDATOR_VERSION}/gtfs-validator-${GTFS_VALIDATOR_VERSION}-cli.jar

FROM eclipse-temurin:${JAVA_VERSION}

# Install Python and other dependencies
RUN apt-get update && \
    apt-get install -y python3 python3-pip python3-venv make curl && \
    rm -rf /var/lib/apt/lists/*

# Download the GTFS Validator JAR
ARG GTFS_VALIDATOR_JAR_URL
RUN echo "Downloading $GTFS_VALIDATOR_JAR_URL"
RUN curl -L -o /opt/gtfs-validator.jar "$GTFS_VALIDATOR_JAR_URL"

# Download and install uv
ADD https://astral.sh/uv/install.sh /uv-installer.sh
RUN sh /uv-installer.sh && rm /uv-installer.sh
ENV PATH="/root/.local/bin/:$PATH"

WORKDIR /app
COPY . .

RUN make venv
ENV PYTHONUNBUFFERED=1
CMD ["make", "dev"]