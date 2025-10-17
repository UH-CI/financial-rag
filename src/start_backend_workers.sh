#!/bin/bash
# Start backend API with 12 workers for parallel fiscal note generation

echo "🚀 Starting backend with 12 workers..."
echo "📖 API Documentation: http://localhost:8200/docs"
echo ""
echo "Press Ctrl+C to stop"
echo ""

uvicorn api:app --host 0.0.0.0 --port 8200 --workers 12
