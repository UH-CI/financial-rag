#!/bin/bash
# Script to start an RQ worker
# Run this inside the api container or wherever the environment is set up

REDIS_URL=${REDIS_URL:-redis://redis:6379}
echo "Starting RQ worker connected to $REDIS_URL"

# Start the worker
# We need to make sure the python path includes /src so it can find 'refbot.tasks'
export PYTHONPATH=$PYTHONPATH:$(pwd)

rq worker --url $REDIS_URL --with-scheduler
