#!/bin/bash
# Script to start an RQ worker
# Run this inside the api container

# Log file for debugging startup issues
LOG_FILE="/src/worker.log"
echo "--- Starting Worker Script at $(date) ---" >> $LOG_FILE

REDIS_URL=${REDIS_URL:-redis://redis:6379}
echo "Using REDIS_URL: $REDIS_URL" >> $LOG_FILE

# Ensure PYTHONPATH includes /src
export PYTHONPATH=$PYTHONPATH:/src
echo "PYTHONPATH: $PYTHONPATH" >> $LOG_FILE
cd /src

# Check if rq is installed
echo "Checking imports..." >> $LOG_FILE
python -c "import rq; import refbot.tasks; print('Imports successful')" >> $LOG_FILE 2>&1
if [ $? -ne 0 ]; then
    echo "ERROR: Import check failed!" >> $LOG_FILE
    exit 1
fi

echo "Starting rq worker..." >> $LOG_FILE

# Run rq worker and redirect output to log file
exec rq worker --url $REDIS_URL --with-scheduler >> $LOG_FILE 2>&1
