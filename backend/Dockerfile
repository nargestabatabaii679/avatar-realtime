###############################################################################
# backend/Dockerfile — Multi-stage build for the FastAPI backend
#
# Stage 1 (builder): Python 3.12-slim — compiles C extensions, downloads
#                    NLTK data, builds wheels.
# Stage 2 (production): NVIDIA CUDA 12.1 + cuDNN 8 runtime on Ubuntu 22.04
#                       — copies the complete Python environment from builder,
#                       installs only runtime system libs, runs as a non-root
#                       user.
#
# Build args:
#   PYTHON_VERSION  default 3.12
#   UID / GID       non-root user (default 1001)
###############################################################################

# ─────────────────────────────────────────────────────────────────────────────
# Stage 1: builder
# ─────────────────────────────────────────────────────────────────────────────
FROM python:3.12-slim AS builder

# Build-time arguments
ARG PYTHON_VERSION=3.12
ARG DEBIAN_FRONTEND=noninteractive

# System build dependencies (compiled C extensions, ffmpeg headers, etc.)
RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
        gcc \
        g++ \
        cmake \
        git \
        curl \
        wget \
        pkg-config \
        libffi-dev \
        libssl-dev \
        libpq-dev \
        # Computer vision / OpenCV dependencies
        libglib2.0-dev \
        libsm-dev \
        libxext-dev \
        libxrender-dev \
        libgl1-mesa-dev \
        # Audio processing
        ffmpeg \
        libavcodec-dev \
        libavformat-dev \
        libavutil-dev \
        libswscale-dev \
        libsndfile1-dev \
        libasound2-dev \
        # Image processing
        libjpeg-dev \
        libpng-dev \
        libwebp-dev \
        libtiff-dev \
    && rm -rf /var/lib/apt/lists/*

# Upgrade pip and install build tools
RUN pip install --upgrade pip setuptools wheel

WORKDIR /build

# Copy requirements first for layer caching.
# If requirements.txt changes, only layers from here forward are invalidated.
COPY requirements.txt .

# Install all Python packages into a dedicated prefix so we can copy them
# cleanly into the production image.
RUN pip install \
        --prefix=/install \
        --no-cache-dir \
        --extra-index-url https://download.pytorch.org/whl/cu121 \
        -r requirements.txt

# Download NLTK corpora required by several NLP sub-packages.
# Done here (with network access) so the production image has no outbound
# network requirement at startup.
RUN python -c "\
import nltk; \
nltk.download('punkt', download_dir='/install/nltk_data'); \
nltk.download('stopwords', download_dir='/install/nltk_data'); \
nltk.download('averaged_perceptron_tagger', download_dir='/install/nltk_data'); \
"

# ─────────────────────────────────────────────────────────────────────────────
# Stage 2: production
# Derive from the official NVIDIA CUDA image so GPU inference just works.
# ─────────────────────────────────────────────────────────────────────────────
FROM nvidia/cuda:12.1.0-cudnn8-runtime-ubuntu22.04 AS production

ARG PYTHON_VERSION=3.12
ARG UID=1001
ARG GID=1001
ARG DEBIAN_FRONTEND=noninteractive

# ── Runtime system dependencies ───────────────────────────────────────────────
# Only what is needed at *runtime* — no compilers, no headers.
RUN apt-get update && apt-get install -y --no-install-recommends \
        # Python runtime (slim subset from Ubuntu repos)
        python3.12 \
        python3.12-distutils \
        python3-pip \
        # Shared libraries used by OpenCV, insightface, onnxruntime
        libgl1-mesa-glx \
        libglib2.0-0 \
        libsm6 \
        libxext6 \
        libxrender1 \
        # FFmpeg runtime (used by imageio-ffmpeg, moviepy, ffmpeg-python)
        ffmpeg \
        libavcodec-extra \
        # Audio
        libsndfile1 \
        # PostgreSQL client (psycopg2 native lib)
        libpq5 \
        # Utilities
        curl \
        wget \
        ca-certificates \
        tini \
    && rm -rf /var/lib/apt/lists/*

# Make python3.12 the default python3
RUN update-alternatives --install /usr/bin/python python /usr/bin/python3.12 1 \
    && update-alternatives --install /usr/bin/python3 python3 /usr/bin/python3.12 1

# ── Copy the built Python environment from the builder stage ─────────────────
COPY --from=builder /install /usr/local
COPY --from=builder /install/nltk_data /usr/share/nltk_data

# ── Non-root user ─────────────────────────────────────────────────────────────
# Running as root inside a container is a security anti-pattern.
RUN groupadd --gid "${GID}" appgroup \
    && useradd  --uid "${UID}" --gid "${GID}" --shell /bin/bash \
                --create-home --no-log-init appuser

# ── Application code ──────────────────────────────────────────────────────────
WORKDIR /app
COPY --chown=appuser:appgroup . .

# ── Model and storage directories ─────────────────────────────────────────────
RUN mkdir -p \
        /opt/models \
        /tmp/avatar-platform/uploads \
        /tmp/avatar-platform/processed \
        /tmp/avatar-platform/cache \
        /tmp/avatar-platform/tmp \
        /tmp/avatar-platform/static \
    && chown -R appuser:appgroup /opt/models /tmp/avatar-platform

USER appuser

# ── Environment variables ─────────────────────────────────────────────────────
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app \
    # CUDA flags
    NVIDIA_VISIBLE_DEVICES=all \
    NVIDIA_DRIVER_CAPABILITIES=compute,utility \
    # Torch tuning: avoid fragmenting GPU memory
    PYTORCH_CUDA_ALLOC_CONF=max_split_size_mb:512 \
    # Suppress insightface "downloading model" chatter
    INSIGHTFACE_HOME=/opt/models/insightface \
    NLTK_DATA=/usr/share/nltk_data \
    # Application defaults (overridden by docker-compose env)
    HOST=0.0.0.0 \
    PORT=8000 \
    WORKERS=1 \
    ENVIRONMENT=production \
    LOG_FORMAT=json

EXPOSE 8000

# ── Health check ──────────────────────────────────────────────────────────────
# K8s liveness / readiness probes should use the HTTP endpoints directly;
# this is a Docker-native fallback.
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:${PORT}/health || exit 1

# tini as PID 1 — correctly propagates signals and reaps zombie processes.
ENTRYPOINT ["/usr/bin/tini", "--"]

# ── Default command ───────────────────────────────────────────────────────────
# Override with `celery -A app.core.celery_app worker ...` for worker containers.
CMD ["uvicorn", "app.main:app", \
     "--host", "0.0.0.0", \
     "--port", "8000", \
     "--workers", "1", \
     "--worker-class", "uvicorn.workers.UvicornWorker", \
     "--proxy-headers", \
     "--forwarded-allow-ips", "*", \
     "--log-config", "/app/log_config.json"]
