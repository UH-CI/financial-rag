#!/bin/bash

# Fiscal Notes Backup Script
# Creates timestamped backups of fiscal notes from production server

set -e

# Configuration
PRODUCTION_HOST="exouser@<YOUR_PRODUCTION_IP>"  # Update this with your production IP
PRODUCTION_PATH="/home/exouser/RAG-system/src/fiscal_notes/generation"
PRODUCTION_BACKUP_DIR="/home/exouser/RAG-system/fiscal_notes_backups"
LOCAL_BACKUP_DIR="./fiscal_notes_backups"
BACKUP_DATE=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="${LOCAL_BACKUP_DIR}/fiscal_notes_${BACKUP_DATE}.tar.gz"

echo "🔄 Starting Fiscal Notes Backup..."
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# Create local backup directory
mkdir -p "${LOCAL_BACKUP_DIR}"

# Check if production directory exists
echo "📡 Connecting to production server..."
if ssh "${PRODUCTION_HOST}" "[ -d ${PRODUCTION_PATH} ]"; then
    echo "✅ Production directory found"
else
    echo "❌ Error: Production directory not found at ${PRODUCTION_PATH}"
    exit 1
fi

# Create backup on production server
echo "📦 Creating backup on production server..."
ssh "${PRODUCTION_HOST}" "cd /home/exouser/RAG-system && tar -czf /tmp/fiscal_notes_backup.tar.gz src/fiscal_notes/generation/"

# Download backup to local machine
echo "⬇️  Downloading backup to local machine..."
scp "${PRODUCTION_HOST}:/tmp/fiscal_notes_backup.tar.gz" "${BACKUP_FILE}"

# Clean up temporary file on production
echo "🧹 Cleaning up production server..."
ssh "${PRODUCTION_HOST}" "rm /tmp/fiscal_notes_backup.tar.gz"

# Get backup size
BACKUP_SIZE=$(du -h "${BACKUP_FILE}" | cut -f1)

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "✅ Backup completed successfully!"
echo "📁 Backup file: ${BACKUP_FILE}"
echo "📊 Backup size: ${BACKUP_SIZE}"
echo ""
echo "📋 All backups:"
ls -lh "${LOCAL_BACKUP_DIR}"/fiscal_notes_*.tar.gz 2>/dev/null || echo "No backups found"

echo ""
echo "💡 To restore this backup:"
echo "   tar -xzf ${BACKUP_FILE}"
echo ""
echo "💡 To copy to production:"
echo "   scp -r src/fiscal_notes/generation/ ${PRODUCTION_HOST}:/home/exouser/RAG-system/src/fiscal_notes/"
