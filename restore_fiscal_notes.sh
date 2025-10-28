#!/bin/bash

# Fiscal Notes Restore Script
# Restores fiscal notes from a backup file

set -e

# Check if backup file is provided
if [ -z "$1" ]; then
    echo "❌ Error: No backup file specified"
    echo ""
    echo "Usage: $0 <backup_file.tar.gz> [destination]"
    echo ""
    echo "Available backups:"
    ls -lh ./fiscal_notes_backups/fiscal_notes_*.tar.gz 2>/dev/null || echo "  No backups found in ./fiscal_notes_backups/"
    echo ""
    echo "Examples:"
    echo "  # Restore to local dev environment:"
    echo "  $0 ./fiscal_notes_backups/fiscal_notes_20251027_152000.tar.gz"
    echo ""
    echo "  # Restore to production server:"
    echo "  $0 ./fiscal_notes_backups/fiscal_notes_20251027_152000.tar.gz production"
    exit 1
fi

BACKUP_FILE="$1"
DESTINATION="${2:-local}"

# Check if backup file exists
if [ ! -f "${BACKUP_FILE}" ]; then
    echo "❌ Error: Backup file not found: ${BACKUP_FILE}"
    exit 1
fi

echo "🔄 Starting Fiscal Notes Restore..."
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "📦 Backup file: ${BACKUP_FILE}"
echo "📊 Backup size: $(du -h "${BACKUP_FILE}" | cut -f1)"
echo "🎯 Destination: ${DESTINATION}"
echo ""

if [ "${DESTINATION}" = "local" ]; then
    # Restore to local dev environment
    echo "⚠️  This will replace your local fiscal notes!"
    echo "   Current location: ./src/fiscal_notes/generation/"
    echo ""
    read -p "Continue? (yes/no): " CONFIRM
    
    if [ "${CONFIRM}" != "yes" ]; then
        echo "❌ Restore cancelled"
        exit 0
    fi
    
    echo "📦 Extracting backup..."
    tar -xzf "${BACKUP_FILE}"
    
    echo "✅ Restore completed successfully!"
    echo "📁 Restored to: ./src/fiscal_notes/generation/"
    
elif [ "${DESTINATION}" = "production" ]; then
    # Restore to production server
    PRODUCTION_HOST="exouser@<YOUR_PRODUCTION_IP>"  # Update this
    
    echo "⚠️  WARNING: This will replace fiscal notes on production!"
    echo "   This may overwrite user annotations!"
    echo ""
    read -p "Are you ABSOLUTELY SURE? (type 'yes' to confirm): " CONFIRM
    
    if [ "${CONFIRM}" != "yes" ]; then
        echo "❌ Restore cancelled"
        exit 0
    fi
    
    echo "📦 Uploading backup to production..."
    scp "${BACKUP_FILE}" "${PRODUCTION_HOST}:/tmp/fiscal_notes_restore.tar.gz"
    
    echo "🔄 Extracting on production server..."
    ssh "${PRODUCTION_HOST}" "cd /home/exouser/RAG-system && tar -xzf /tmp/fiscal_notes_restore.tar.gz"
    
    echo "🧹 Cleaning up..."
    ssh "${PRODUCTION_HOST}" "rm /tmp/fiscal_notes_restore.tar.gz"
    
    echo "✅ Restore to production completed successfully!"
    
else
    echo "❌ Error: Invalid destination '${DESTINATION}'"
    echo "   Valid options: 'local' or 'production'"
    exit 1
fi

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "✅ Restore completed!"
