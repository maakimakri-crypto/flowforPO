#!/usr/bin/env bash
# ProjectFlow Backup Script
# Run manually or via cron: 0 2 * * * /app/scripts/backup.sh
# Requires: zip, gpg (optional for encryption)

set -euo pipefail

APP_DIR="${APP_DIR:-$(dirname "$0")}"
DATA_DIR="${APP_DIR}/data"
BACKUP_DIR="${BACKUP_DIR:-/backups}"
RETENTION_DAYS="${RETENTION_DAYS:-30}"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
HOSTNAME=$(hostname)
BACKUP_NAME="projectflow_${HOSTNAME}_${TIMESTAMP}"

mkdir -p "$BACKUP_DIR"

echo "[$(date)] Starting backup..."

# Copy files to temp dir to ensure consistent snapshot
TMPDIR=$(mktemp -d)
trap "rm -rf $TMPDIR" EXIT

cp -r "$DATA_DIR" "$TMPDIR/data"

# Create archive (skip gitkeep files)
cd "$TMPDIR"
zip -r "$BACKUP_DIR/${BACKUP_NAME}.zip" data/ -x "data/.gitkeep" 2>/dev/null || true

# Optional GPG encryption (set BACKUP_PASSPHRASE env var to enable)
if [[ -n "${BACKUP_PASSPHRASE:-}" ]]; then
    echo "[$(date)] Encrypting backup..."
    gpg --batch --yes --passphrase "$BACKUP_PASSPHRASE" \
        -c --cipher-algo AES256 \
        "$BACKUP_DIR/${BACKUP_NAME}.zip"
    rm "$BACKUP_DIR/${BACKUP_NAME}.zip"
    echo "[$(date)] Encrypted backup: ${BACKUP_NAME}.zip.gpg"
else
    echo "[$(date)] Unencrypted backup: ${BACKUP_NAME}.zip (set BACKUP_PASSPHRASE to encrypt)"
fi

# Prune old backups
echo "[$(date)] Pruning backups older than $RETENTION_DAYS days..."
find "$BACKUP_DIR" -name "projectflow_${HOSTNAME}_*.zip*" -mtime "+$RETENTION_DAYS" -delete

echo "[$(date)] Backup complete: $(du -sh "$BACKUP_DIR/${BACKUP_NAME}"* | cut -f1)"

# Optional: push to remote (S3, rclone, rsync)
# Uncomment and configure for your storage:
# rclone copy "$BACKUP_DIR/${BACKUP_NAME}.zip.gpg" remote:bucket/projectflow-backups/ --quiet

echo "[$(date)] Done."
