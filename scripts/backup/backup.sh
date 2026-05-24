#!/usr/bin/env bash
set -euo pipefail

BACKUP_DIR="${BACKUP_DIR:-/opt/backups/avatar-platform}"
RETAIN_DAYS="${RETAIN_DAYS:-30}"
TIMESTAMP=$(date +%Y%m%d-%H%M%S)
BACKUP_NAME="avatar-platform-$TIMESTAMP"
TMP_DIR="$BACKUP_DIR/tmp/$BACKUP_NAME"

info()    { echo "[$(date '+%H:%M:%S')] INFO: $*"; }
success() { echo "[$(date '+%H:%M:%S')] OK: $*"; }
error()   { echo "[$(date '+%H:%M:%S')] ERROR: $*"; exit 1; }

mkdir -p "$TMP_DIR" "$BACKUP_DIR"

info "Starting backup: $BACKUP_NAME"

# ─── PostgreSQL ───────────────────────────────────────────────────────
info "Backing up PostgreSQL..."
docker compose exec -T postgres pg_dumpall -U postgres | gzip > "$TMP_DIR/postgres.sql.gz"
success "PostgreSQL backup complete ($(du -sh $TMP_DIR/postgres.sql.gz | cut -f1))"

# ─── MinIO ───────────────────────────────────────────────────────────
info "Backing up MinIO storage..."
MINIO_BACKUP="$TMP_DIR/minio"
mkdir -p "$MINIO_BACKUP"
# Use mc (MinIO client) to mirror
if command -v mc >/dev/null 2>&1; then
    mc alias set local http://localhost:9000 "$MINIO_ACCESS_KEY" "$MINIO_SECRET_KEY" 2>/dev/null || true
    for bucket in avatars voices videos documents; do
        mc mirror "local/$bucket" "$MINIO_BACKUP/$bucket" --overwrite 2>/dev/null || warn "Bucket $bucket may be empty"
    done
else
    warn "MinIO client (mc) not installed. Skipping MinIO backup."
fi
success "MinIO backup complete"

# ─── Qdrant ──────────────────────────────────────────────────────────
info "Backing up Qdrant collections..."
curl -s "http://localhost:6333/collections" | python3 -c "
import json, sys
data = json.load(sys.stdin)
collections = [c['name'] for c in data.get('result', {}).get('collections', [])]
print('\n'.join(collections))
" | while read -r collection; do
    curl -s -o "$TMP_DIR/qdrant_${collection}.json" \
        "http://localhost:6333/collections/$collection/points/scroll?limit=10000"
done
success "Qdrant backup complete"

# ─── Compress and encrypt ─────────────────────────────────────────────
info "Compressing backup..."
tar -czf "$BACKUP_DIR/$BACKUP_NAME.tar.gz" -C "$BACKUP_DIR/tmp" "$BACKUP_NAME"

if [[ -n "${BACKUP_ENCRYPTION_KEY:-}" ]]; then
    info "Encrypting backup..."
    gpg --batch --symmetric --passphrase "$BACKUP_ENCRYPTION_KEY" \
        --output "$BACKUP_DIR/$BACKUP_NAME.tar.gz.gpg" \
        "$BACKUP_DIR/$BACKUP_NAME.tar.gz"
    rm "$BACKUP_DIR/$BACKUP_NAME.tar.gz"
    FINAL_FILE="$BACKUP_DIR/$BACKUP_NAME.tar.gz.gpg"
else
    FINAL_FILE="$BACKUP_DIR/$BACKUP_NAME.tar.gz"
fi

BACKUP_SIZE=$(du -sh "$FINAL_FILE" | cut -f1)
success "Backup created: $FINAL_FILE ($BACKUP_SIZE)"

# ─── Upload to S3 (optional) ─────────────────────────────────────────
if [[ -n "${S3_BACKUP_BUCKET:-}" ]] && command -v aws >/dev/null 2>&1; then
    info "Uploading to S3: s3://$S3_BACKUP_BUCKET/"
    aws s3 cp "$FINAL_FILE" "s3://$S3_BACKUP_BUCKET/$(basename $FINAL_FILE)"
    success "Uploaded to S3"
fi

# ─── Cleanup old backups ─────────────────────────────────────────────
info "Removing backups older than $RETAIN_DAYS days..."
find "$BACKUP_DIR" -maxdepth 1 -name "avatar-platform-*.tar.gz*" \
    -mtime "+$RETAIN_DAYS" -delete
rm -rf "$BACKUP_DIR/tmp"

success "Backup process complete: $BACKUP_NAME"
info "Backup size: $BACKUP_SIZE"
