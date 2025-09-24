# Redis Setup for Multi-Worker Support

## Quick Setup

### Option 1: Using Docker (Recommended)
```bash
# Start Redis in Docker
docker run -d --name redis -p 6379:6379 redis:latest

# Or add to your docker-compose.yml:
# redis:
#   image: redis:latest
#   ports:
#     - "6379:6379"
```

### Option 2: Install Redis locally
```bash
# macOS
brew install redis
brew services start redis

# Ubuntu/Debian
sudo apt update
sudo apt install redis-server
sudo systemctl start redis

# Windows
# Download from https://redis.io/download
```

## Install Python Redis Client
```bash
pip install redis
```

## Verify Setup
```bash
# Test Redis connection
redis-cli ping
# Should return: PONG
```

## What This Enables

✅ **Shared job tracking** across all 4 uvicorn workers
✅ **WebSocket broadcasts** reach users connected to any worker  
✅ **No duplicate jobs** - if Worker A starts a job, Workers B, C, D know about it
✅ **Automatic cleanup** - jobs expire after 1 hour

## Fallback Behavior

If Redis is not available, the system automatically falls back to:
- In-memory job tracking (single worker only)
- Local WebSocket broadcasts only
- Warning message in console

The API will still work, but multi-worker coordination will be limited.
