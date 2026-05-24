#!/usr/bin/env bash
set -euo pipefail

# ═══════════════════════════════════════════════════════════════════════
# Avatar Platform — Automated Installation Script
# ═══════════════════════════════════════════════════════════════════════

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; BLUE='\033[0;34m'; NC='\033[0m'
info()    { echo -e "${BLUE}[INFO]${NC} $*"; }
success() { echo -e "${GREEN}[OK]${NC} $*"; }
warn()    { echo -e "${YELLOW}[WARN]${NC} $*"; }
error()   { echo -e "${RED}[ERROR]${NC} $*"; exit 1; }

INSTALL_DIR="${INSTALL_DIR:-/opt/avatar-realtime}"
COMPOSE_FILE="$INSTALL_DIR/docker-compose.yml"

echo ""
echo "╔══════════════════════════════════════════╗"
echo "║    AI Digital Human Platform Setup       ║"
echo "║    Version 1.0.0                         ║"
echo "╚══════════════════════════════════════════╝"
echo ""

# ─── Check prerequisites ─────────────────────────────────────────────
info "Checking prerequisites..."

command -v docker >/dev/null 2>&1 || error "Docker not found. Install from https://docs.docker.com/get-docker/"
command -v docker-compose >/dev/null 2>&1 || docker compose version >/dev/null 2>&1 || error "Docker Compose not found."

DOCKER_VERSION=$(docker --version | grep -oP '\d+\.\d+')
info "Docker version: $DOCKER_VERSION"

# Check GPU (optional)
if command -v nvidia-smi >/dev/null 2>&1; then
    GPU_NAME=$(nvidia-smi --query-gpu=name --format=csv,noheader | head -1)
    success "GPU detected: $GPU_NAME"
    HAS_GPU=true
else
    warn "No NVIDIA GPU detected. AI tasks will run on CPU (slower)."
    HAS_GPU=false
fi

# ─── Setup environment ───────────────────────────────────────────────
info "Configuring environment..."

if [[ ! -f "$INSTALL_DIR/.env" ]]; then
    cp "$INSTALL_DIR/.env.example" "$INSTALL_DIR/.env"

    # Generate secure random keys
    SECRET_KEY=$(python3 -c "import secrets; print(secrets.token_hex(32))")
    JWT_SECRET=$(python3 -c "import secrets; print(secrets.token_hex(32))")
    POSTGRES_PASS=$(python3 -c "import secrets; print(secrets.token_urlsafe(20))")
    MINIO_SECRET=$(python3 -c "import secrets; print(secrets.token_urlsafe(20))")

    sed -i "s/SECRET_KEY=.*/SECRET_KEY=$SECRET_KEY/" "$INSTALL_DIR/.env"
    sed -i "s/JWT_SECRET_KEY=.*/JWT_SECRET_KEY=$JWT_SECRET/" "$INSTALL_DIR/.env"
    sed -i "s/POSTGRES_PASSWORD=.*/POSTGRES_PASSWORD=$POSTGRES_PASS/" "$INSTALL_DIR/.env"
    sed -i "s/MINIO_SECRET_KEY=.*/MINIO_SECRET_KEY=$MINIO_SECRET/" "$INSTALL_DIR/.env"

    success "Generated secure random credentials in .env"
    warn "Please review and update .env with your API keys (OPENAI_API_KEY, SENTRY_DSN, etc.)"
else
    info ".env already exists, skipping generation"
fi

# ─── Pull Docker images ───────────────────────────────────────────────
info "Pulling Docker images (this may take a few minutes)..."
cd "$INSTALL_DIR"
docker compose pull

# ─── Start services ──────────────────────────────────────────────────
info "Starting services..."
docker compose up -d postgres redis qdrant minio

info "Waiting for services to be healthy..."
sleep 10

# Wait for PostgreSQL
until docker compose exec -T postgres pg_isready -U postgres >/dev/null 2>&1; do
    echo -n "."; sleep 2
done
success "PostgreSQL ready"

# Wait for Redis
until docker compose exec -T redis redis-cli ping >/dev/null 2>&1; do
    echo -n "."; sleep 2
done
success "Redis ready"

# ─── Database setup ───────────────────────────────────────────────────
info "Running database migrations..."
docker compose run --rm backend alembic upgrade head
success "Database migrations complete"

# ─── Initialize admin user ────────────────────────────────────────────
info "Creating default admin user..."
read -p "Admin email [admin@avatarplatform.local]: " ADMIN_EMAIL
ADMIN_EMAIL=${ADMIN_EMAIL:-admin@avatarplatform.local}
read -s -p "Admin password: " ADMIN_PASS
echo ""
[[ ${#ADMIN_PASS} -lt 8 ]] && error "Password must be at least 8 characters"

docker compose run --rm backend python scripts/setup/init_db.py \
    --admin-email "$ADMIN_EMAIL" \
    --admin-password "$ADMIN_PASS" \
    --org-name "Default Organization"

success "Admin user created: $ADMIN_EMAIL"

# ─── Start all services ───────────────────────────────────────────────
info "Starting all services..."
docker compose up -d
sleep 10

# ─── Health check ────────────────────────────────────────────────────
info "Running health check..."
if curl -sf http://localhost:8000/health/ready >/dev/null; then
    success "API backend is healthy"
else
    warn "API backend health check failed. Check: docker compose logs backend"
fi

# ─── Download AI models ───────────────────────────────────────────────
info "Downloading AI models (this may take 20-40 minutes depending on your connection)..."
read -p "Download models now? [Y/n]: " DOWNLOAD_MODELS
if [[ "${DOWNLOAD_MODELS:-Y}" =~ ^[Yy]$ ]]; then
    docker compose exec backend python scripts/setup/download_models.py
    success "AI models downloaded"
else
    warn "Skipping model download. Run manually: docker compose exec backend python scripts/setup/download_models.py"
fi

# ─── Print access info ────────────────────────────────────────────────
echo ""
echo "╔══════════════════════════════════════════════════════════╗"
echo "║           Installation Complete!                          ║"
echo "╠══════════════════════════════════════════════════════════╣"
echo "║  Frontend:       http://localhost:3000                    ║"
echo "║  API:            http://localhost:8000                    ║"
echo "║  API Docs:       http://localhost:8000/docs               ║"
echo "║  MinIO Console:  http://localhost:9001                    ║"
echo "║  Flower:         http://localhost:5555                    ║"
echo "║  Grafana:        http://localhost:3001 (admin/admin)      ║"
echo "╠══════════════════════════════════════════════════════════╣"
echo "║  Admin Email:    $ADMIN_EMAIL"
echo "╚══════════════════════════════════════════════════════════╝"
echo ""
info "Next steps:"
echo "  1. Open http://localhost:3000 and log in with your admin credentials"
echo "  2. Update .env with your OPENAI_API_KEY for GPT-4 support"
echo "  3. Create your first avatar in Avatar Studio"
echo ""
