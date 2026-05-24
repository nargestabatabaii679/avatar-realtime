# Installation Guide — AI Digital Human Platform

## Prerequisites

### Hardware Requirements

| Component | Minimum | Recommended | Enterprise |
|-----------|---------|-------------|------------|
| CPU | 8 cores | 16 cores | 32+ cores |
| RAM | 32 GB | 64 GB | 128+ GB |
| GPU | RTX 3080 (10GB VRAM) | RTX 4090 (24GB VRAM) | A100 (80GB) |
| Storage | 500 GB SSD | 2 TB NVMe | 10+ TB RAID |
| Network | 100 Mbps | 1 Gbps | 10 Gbps |

### Software Requirements

- Ubuntu 22.04 LTS or RHEL 9 (recommended)
- Docker Engine 26.x+
- Docker Compose v2.x+
- NVIDIA Driver 535+ (for GPU support)
- NVIDIA Container Toolkit
- Git 2.x+

### GPU Driver Setup (Ubuntu)

```bash
# Add NVIDIA package repository
wget https://developer.download.nvidia.com/compute/cuda/repos/ubuntu2204/x86_64/cuda-keyring_1.1-1_all.deb
sudo dpkg -i cuda-keyring_1.1-1_all.deb
sudo apt update

# Install NVIDIA drivers
sudo apt install -y nvidia-driver-535

# Install CUDA toolkit
sudo apt install -y cuda-toolkit-12-3

# Install NVIDIA Container Toolkit
curl -fsSL https://nvidia.github.io/libnvidia-container/gpgkey | sudo gpg --dearmor -o /usr/share/keyrings/nvidia-container-toolkit-keyring.gpg
curl -s -L https://nvidia.github.io/libnvidia-container/stable/deb/nvidia-container-toolkit.list | \
  sed 's#deb https://#deb [signed-by=/usr/share/keyrings/nvidia-container-toolkit-keyring.gpg] https://#g' | \
  sudo tee /etc/apt/sources.list.d/nvidia-container-toolkit.list
sudo apt update && sudo apt install -y nvidia-container-toolkit
sudo nvidia-ctk runtime configure --runtime=docker
sudo systemctl restart docker

# Verify GPU access
nvidia-smi
docker run --rm --gpus all nvidia/cuda:12.3.0-base-ubuntu22.04 nvidia-smi
```

---

## Quick Start (Development)

```bash
# 1. Clone the repository
git clone https://github.com/your-org/avatar-realtime.git
cd avatar-realtime

# 2. Run the setup script
chmod +x scripts/setup/install.sh
./scripts/setup/install.sh

# 3. Configure environment
cp .env.example .env
nano .env  # Fill in required values

# 4. Start services
docker compose up -d

# 5. Initialize database
docker compose exec backend python scripts/setup/init_db.py

# 6. Download AI models
docker compose exec backend python scripts/setup/download_models.py

# 7. Access the platform
echo "Frontend: http://localhost:3000"
echo "API: http://localhost:8000"
echo "API Docs: http://localhost:8000/docs"
echo "MinIO Console: http://localhost:9001"
echo "Flower (Celery): http://localhost:5555"
echo "Grafana: http://localhost:3001"
```

---

## Step-by-Step Installation

### Step 1: System Preparation

```bash
# Update system
sudo apt update && sudo apt upgrade -y

# Install Docker
curl -fsSL https://get.docker.com | bash
sudo usermod -aG docker $USER
newgrp docker

# Install Docker Compose
sudo apt install -y docker-compose-plugin

# Verify
docker --version
docker compose version
```

### Step 2: Clone Repository

```bash
git clone https://github.com/your-org/avatar-realtime.git
cd avatar-realtime
```

### Step 3: Configure Environment Variables

```bash
cp .env.example .env
```

Edit `.env` and set:

```bash
# REQUIRED: Generate a secure secret key
SECRET_KEY=$(python3 -c "import secrets; print(secrets.token_hex(32))")

# REQUIRED: Database password
POSTGRES_PASSWORD=$(python3 -c "import secrets; print(secrets.token_urlsafe(24))")

# REQUIRED: MinIO credentials
MINIO_ACCESS_KEY=admin
MINIO_SECRET_KEY=$(python3 -c "import secrets; print(secrets.token_urlsafe(24))")

# OPTIONAL: OpenAI (for GPT-4 support)
OPENAI_API_KEY=sk-...

# OPTIONAL: Sentry (for error monitoring)
SENTRY_DSN=https://...@sentry.io/...
```

### Step 4: Download AI Models

The platform requires several AI models (~20-40GB total):

```bash
# Create models directory
mkdir -p models/{liveportrait,musetalk,wav2lip,whisper,xtts-v2,insightface}

# Run model download script
docker compose run --rm backend python scripts/setup/download_models.py

# Models downloaded:
# - WhisperLarge-v3: ~3GB
# - XTTS-v2: ~2GB  
# - InsightFace buffalo_l: ~500MB
# - LivePortrait: ~4GB
# - MuseTalk: ~3GB
# - Wav2Lip GAN: ~500MB
# - multilingual-e5-large: ~600MB
```

### Step 5: Start Services

```bash
# Start all services
docker compose up -d

# Verify all containers are healthy
docker compose ps

# Check logs
docker compose logs -f backend
docker compose logs -f worker-gpu
```

### Step 6: Initialize Database

```bash
# Run migrations
docker compose exec backend alembic upgrade head

# Create super admin
docker compose exec backend python scripts/setup/init_db.py \
  --admin-email admin@yourcompany.com \
  --admin-password "YourSecurePassword123!" \
  --org-name "Your Company"
```

### Step 7: Configure Storage Buckets

```bash
# MinIO buckets are created automatically on startup
# Verify via MinIO console: http://localhost:9001
# Login: MINIO_ACCESS_KEY / MINIO_SECRET_KEY
```

### Step 8: Verify Installation

```bash
# Health check
curl http://localhost:8000/health/ready

# Expected response:
# {"status": "ready", "database": "connected", "redis": "connected", "minio": "connected"}

# Test frontend
curl -I http://localhost:3000

# GPU check
curl http://localhost:8000/health/gpu
```

---

## Production Deployment

### Option A: Docker Compose (Single Server)

```bash
# Use production compose file
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d

# Key differences from development:
# - No hot reload
# - Resource limits enforced
# - Log aggregation
# - SSL/TLS via Nginx
```

### Configure SSL/TLS

```bash
# Install Certbot
sudo apt install -y certbot

# Obtain certificate (replace with your domain)
sudo certbot certonly --standalone -d avatarplatform.yourdomain.com

# Update nginx config with SSL paths
# Edit infrastructure/nginx/nginx.conf:
# ssl_certificate /etc/letsencrypt/live/avatarplatform.yourdomain.com/fullchain.pem;
# ssl_certificate_key /etc/letsencrypt/live/avatarplatform.yourdomain.com/privkey.pem;

# Mount certificates in docker-compose
# volumes:
#   - /etc/letsencrypt:/etc/letsencrypt:ro

# Auto-renew
sudo crontab -e
# Add: 0 0 1 * * certbot renew && docker compose exec nginx nginx -s reload
```

### Option B: Kubernetes Deployment

```bash
# Prerequisites: kubectl, helm, kustomize installed
# Kubernetes cluster with GPU nodes configured

# Add NVIDIA GPU operator
helm repo add nvidia https://helm.ngc.nvidia.com/nvidia
helm install gpu-operator nvidia/gpu-operator

# Apply base manifests
kubectl apply -k infrastructure/kubernetes/base/

# Apply production overlay
kubectl apply -k infrastructure/kubernetes/overlays/production/

# Check deployment
kubectl get pods -n avatar-platform
kubectl get services -n avatar-platform

# Get ingress IP/hostname
kubectl get ingress -n avatar-platform
```

---

## Configuration Reference

### Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `SECRET_KEY` | Yes | - | JWT signing key (min 32 chars) |
| `POSTGRES_HOST` | Yes | `postgres` | PostgreSQL host |
| `POSTGRES_PASSWORD` | Yes | - | Database password |
| `REDIS_URL` | Yes | `redis://redis:6379/0` | Redis connection URL |
| `MINIO_ENDPOINT` | Yes | `minio:9000` | MinIO endpoint |
| `MINIO_ACCESS_KEY` | Yes | - | MinIO access key |
| `MINIO_SECRET_KEY` | Yes | - | MinIO secret key |
| `QDRANT_HOST` | Yes | `qdrant` | Qdrant host |
| `OPENAI_API_KEY` | No | - | OpenAI API key |
| `DEEPSEEK_API_KEY` | No | - | DeepSeek API key |
| `SENTRY_DSN` | No | - | Sentry error tracking DSN |
| `CORS_ORIGINS` | Yes | `["http://localhost:3000"]` | Allowed CORS origins |
| `CUDA_VISIBLE_DEVICES` | No | `0` | GPU device index |
| `WHISPER_MODEL_SIZE` | No | `large-v3` | Whisper model size |

### Model Configuration

Edit `app/core/config.py` to configure which models to use:

```python
# Primary animation engine
ANIMATION_ENGINE = "liveportrait"  # or "wav2lip"

# TTS engine
TTS_ENGINE = "xtts"  # or "cosyvoice", "f5tts"

# LLM provider  
LLM_PROVIDER = "openai"  # or "deepseek", "ollama"
LLM_MODEL = "gpt-4o"  # or "deepseek-chat", "llama3.1:70b"

# Real-time lip sync
REALTIME_LIPSYNC = "musetalk"  # or "wav2lip"
```

---

## Troubleshooting

### GPU Not Detected

```bash
# Verify NVIDIA runtime
docker info | grep -i runtime

# Check GPU in container
docker run --rm --gpus all nvidia/cuda:12.3.0-base-ubuntu22.04 nvidia-smi

# If error: restart Docker daemon
sudo systemctl restart docker
```

### Out of Memory (GPU)

```bash
# Reduce batch sizes in .env
AVATAR_BATCH_SIZE=1
VIDEO_BATCH_FRAMES=30

# Check GPU usage
watch -n 1 nvidia-smi

# Clear GPU memory manually
docker compose exec worker-gpu python -c "import torch; torch.cuda.empty_cache()"
```

### Database Connection Issues

```bash
# Check PostgreSQL logs
docker compose logs postgres

# Test connection
docker compose exec backend python -c "
from app.core.database import engine
import asyncio
async def test():
    async with engine.connect() as conn:
        result = await conn.execute('SELECT 1')
        print('DB OK:', result.scalar())
asyncio.run(test())
"
```

### Storage Issues

```bash
# Check MinIO health
curl http://localhost:9000/minio/health/live

# List buckets
docker compose exec minio mc ls local/

# Check storage usage
docker compose exec backend python -c "
from app.services.storage.minio_service import get_storage_stats
import asyncio
print(asyncio.run(get_storage_stats()))
"
```

---

## Offline Deployment

For air-gapped environments:

```bash
# 1. On internet-connected machine, export all images
docker compose pull
docker save \
  postgres:16 redis:7-alpine qdrant/qdrant:latest \
  minio/minio:latest nginx:alpine node:20-alpine \
  nvidia/cuda:12.1.0-cudnn8-runtime-ubuntu22.04 \
  | gzip > avatar-platform-images.tar.gz

# 2. Copy to air-gapped server
scp avatar-platform-images.tar.gz server:/opt/

# 3. Load images on air-gapped server
docker load < /opt/avatar-platform-images.tar.gz

# 4. Copy model files
rsync -av models/ server:/opt/avatar-realtime/models/

# 5. Build backend image locally
docker build -t avatar-backend:local ./backend

# 6. Deploy
docker compose up -d
```

---

## Backup and Recovery

### Automated Backup

```bash
# Configure backup schedule
crontab -e
# 0 2 * * * /opt/avatar-realtime/scripts/backup/backup.sh >> /var/log/avatar-backup.log 2>&1

# Manual backup
./scripts/backup/backup.sh

# Backups stored in: /opt/backups/avatar-platform/
# Format: avatar-platform-YYYYMMDD-HHMMSS.tar.gz.gpg
```

### Restore

```bash
# Restore from backup
./scripts/backup/restore.sh /opt/backups/avatar-platform/avatar-platform-20240101-020000.tar.gz.gpg

# This will:
# 1. Stop all services
# 2. Restore PostgreSQL
# 3. Restore MinIO
# 4. Restore Qdrant
# 5. Restart services
```

---

## Monitoring

Access monitoring dashboards:

- **Grafana**: http://your-server:3001 (admin/admin, change immediately)
- **Prometheus**: http://your-server:9090
- **Flower (Celery)**: http://your-server:5555
- **API Docs**: http://your-server:8000/docs

Import pre-built Grafana dashboards from `infrastructure/monitoring/grafana/dashboards/`.
