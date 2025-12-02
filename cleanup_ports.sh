#!/bin/bash

# Emergency port cleanup script
# Run this on the server if deployment fails due to port conflicts

echo "🔍 Checking current port usage..."
netstat -tlnp | grep -E ":(6379|8200|3000|4444)"

echo ""
echo "🛑 Stopping all Docker containers..."
docker stop $(docker ps -q) 2>/dev/null || true

echo ""
echo "🧹 Removing stopped containers..."
docker container prune -f

echo ""
echo "💀 Killing processes on specific ports..."

# Kill processes using our ports
for PORT in 6379 8200 3000 4444; do
    PID=$(lsof -ti:$PORT 2>/dev/null || true)
    if [ -n "$PID" ]; then
        echo "Killing process $PID using port $PORT"
        kill -9 $PID 2>/dev/null || true
    fi
done

echo ""
echo "⏳ Waiting for ports to be released..."
sleep 5

echo ""
echo "✅ Final port status:"
netstat -tlnp | grep -E ":(6379|8200|3000|4444)" || echo "All ports are now free!"

echo ""
echo "📋 Remaining Docker containers:"
docker ps
