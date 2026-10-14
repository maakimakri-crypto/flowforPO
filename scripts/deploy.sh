#!/usr/bin/env bash
# ProjectFlow Deployment Guide
# =============================================================
# 1. Prerequisites
#    - Docker & Docker Compose installed
#    - Domain name pointing to server (for HTTPS)
#    - Server with root/sudo access
#
# 2. Transfer files to server
#    rsync -avz --exclude='data/' --exclude='.venv/' \
#          --exclude='__pycache__/' projectflow_mvp/ user@server:/opt/projectflow/
#
# 3. On server: configure environment
#    cd /opt/projectflow
#    cp .env.example .env
#    nano .env   # set SESSION_SECRET
#
# 4. Generate strong SESSION_SECRET:
#    openssl rand -hex 32
#    # paste result into SESSION_SECRET in .env
#
# 5. Update Caddyfile with your domain:
#    nano Caddyfile
#    # replace projectflow.localhost with your.domain.com
#
# 6. Set proper permissions
#    chmod 600 .env
#    mkdir -p data uploads
#    chmod 755 scripts/backup.sh
#
# 7. Pull HTTPS certificate (Caddy auto-manages)
#    # First start → Caddy fetches Let's Encrypt cert
#    docker compose up -d
#
# 8. Create initial admin
#    curl -X POST http://localhost/api/setup \
#      -H "Content-Type: application/json" \
#      -d '{"username":"admin","password":"YourSecurePassword123!"}'
#
# 9. Set up automated backups
#    # Add to crontab:
#    0 2 * * * APP_DIR=/opt/projectflow BACKUP_DIR=/backups /opt/projectflow/scripts/backup.sh
#
# 10. Verify
#     docker compose ps
#     curl -I https://your.domain.com/api/health
# =============================================================

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

cd "$PROJECT_DIR"

echo "=== ProjectFlow Deployment ==="

# Check docker
if ! command -v docker &>/dev/null; then
    echo "ERROR: Docker is not installed"
    exit 1
fi

# Check .env
if [[ ! -f .env ]]; then
    echo "ERROR: .env not found. Run: cp .env.example .env"
    exit 1
fi

# Validate SESSION_SECRET is set
source .env
if [[ "$SESSION_SECRET" == "REPLACE_WITH_LONG_RANDOM_SECRET" ]]; then
    echo "ERROR: SESSION_SECRET must be set in .env"
    echo "Run: openssl rand -hex 32"
    exit 1
fi

# Ensure data directories exist
mkdir -p data uploads
chmod 755 data uploads

echo "Starting ProjectFlow..."
docker compose up -d --build

echo "Waiting for health check..."
for i in {1..30}; do
    if curl -sf http://localhost:8000/api/health > /dev/null 2>&1; then
        echo "✓ Application is healthy"
        break
    fi
    sleep 1
done

echo ""
echo "=== Deployment Summary ==="
echo "  App URL: http://localhost:8000"
echo "  Health:  http://localhost:8000/api/health"
echo "  Docs:    http://localhost:8000/docs"
echo ""
echo "⚠️  First: create admin account before exposing to public!"
echo "⚠️  Run: curl -X POST http://localhost:8000/api/setup ..."
