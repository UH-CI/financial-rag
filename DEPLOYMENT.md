# House Finance Deployment Guide

This guide covers multiple deployment options for the House Finance API and test interface.

## 📊 Database Size Analysis

- **ChromaDB Total**: ~220MB
- **Main data file**: 90MB (under GitHub's 100MB limit)
- **Collections**: Pre-processed and ready to use
- **✅ Safe to include in repository**

## 🚀 Deployment Options (Ranked by Ease)

### 1. 🥇 **EASIEST: GitHub + Direct Deployment**

**Best for**: Quick demos, development servers, small deployments

#### Steps:
1. **Push to GitHub** (ChromaDB included):
   ```bash
   git add .
   git commit -m "Add complete application with ChromaDB"
   git push origin main
   ```

2. **Deploy on server**:
   ```bash
   # Clone and run
   git clone https://github.com/yourusername/house-finance.git
   cd house-finance
   ./deploy.sh local
   ```

**Pros**: 
- ✅ Simplest setup
- ✅ No Docker knowledge required
- ✅ Database included, no processing needed
- ✅ Works on any server with Python

**Cons**: 
- ❌ Requires Python environment setup
- ❌ Less isolated than containers

---

### 2. 🥈 **Docker Hub (Recommended for Production)**

**Best for**: Production deployments, scalability, isolation

#### Steps:
1. **Build and push image**:
   ```bash
   ./deploy.sh build
   ./deploy.sh push
   ```

2. **Deploy on server**:
   ```bash
   # Single command deployment
   docker run -d -p 8000:8000 -p 8081:8080 yourusername/house-finance:latest
   ```

**Pros**: 
- ✅ Complete isolation
- ✅ Consistent environment
- ✅ Easy scaling
- ✅ One-command deployment

**Cons**: 
- ❌ Requires Docker knowledge
- ❌ Larger image size (~1GB)

---

### 3. 🥉 **GitHub + Docker Compose**

**Best for**: Team deployments, development environments

#### Steps:
1. **Clone and deploy**:
   ```bash
   git clone https://github.com/yourusername/house-finance.git
   cd house-finance
   ./deploy.sh docker
   ```

**Pros**: 
- ✅ Best of both worlds
- ✅ Easy to modify
- ✅ Version controlled

**Cons**: 
- ❌ Requires Docker + Git

---

## 🛠️ Quick Start Commands

### Local Development
```bash
./deploy.sh local
```
- API: http://localhost:8000
- Test Interface: http://localhost:8081/budget_test_interface.html

### Docker Production
```bash
./deploy.sh docker
```
- Same URLs as above
- Runs in containers

### Check Status
```bash
./deploy.sh status
```

### Stop Services
```bash
./deploy.sh stop
```

## 🌐 Server Requirements

### Minimum Requirements:
- **CPU**: 1 core
- **RAM**: 2GB (4GB recommended)
- **Storage**: 1GB free space
- **OS**: Linux/macOS/Windows

### For Python deployment:
- Python 3.11+
- pip
- 2GB RAM for ChromaDB

### For Docker deployment:
- Docker 20.10+
- Docker Compose 2.0+
- 4GB RAM recommended

## 🔧 Configuration

### Environment Variables
Copy `src/.env.example` to `src/.env` and configure:
```bash
# API Keys
GOOGLE_API_KEY=your_gemini_api_key
OPENAI_API_KEY=your_openai_key

# ChromaDB Settings
CHROMA_PERSIST_DIRECTORY=./chroma_db
CHROMA_DISTANCE_FUNCTION=cosine

# API Settings
API_HOST=0.0.0.0
API_PORT=8000
```

### Port Configuration (Updated for Server Compatibility)
- **8000**: API server (no conflicts)
- **8081**: Test interface (changed from 8080 to avoid Watchtower conflict)
- **80**: Nginx proxy (optional)

**Note**: Port 8081 is used instead of 8080 to avoid conflicts with existing Guacamole/Watchtower services.

## 🚨 Production Considerations

### Security
- Use environment variables for API keys
- Set up HTTPS with reverse proxy
- Configure firewall rules
- Use non-root user in containers

### Performance
- ChromaDB is already optimized with 220MB of pre-processed data
- Consider adding Redis for caching if needed
- Monitor memory usage (ChromaDB loads into RAM)

### Monitoring
- API has built-in health checks
- Docker Compose includes health monitoring
- Consider adding logging aggregation

## 📝 Troubleshooting

### Common Issues:

1. **Port conflicts**:
   ```bash
   # Check what's using ports
   lsof -i :8000
   lsof -i :8081
   
   # Kill processes or use different ports
   ./deploy.sh stop
   ```

2. **ChromaDB not found**:
   ```bash
   # Ensure ChromaDB directory exists
   ls -la src/chroma_db/
   
   # If missing, re-clone repository
   ```

3. **API key errors**:
   ```bash
   # Check environment file
   cat src/.env
   
   # Ensure API keys are set
   ```

4. **Docker build fails**:
   ```bash
   # Clean Docker cache
   docker system prune -a
   
   # Rebuild
   ./deploy.sh build
   ```

## 🎯 Recommendation

**For your use case, I recommend Option 1 (GitHub + Direct Deployment)** because:

1. ✅ **ChromaDB is small enough** (220MB) to include in repo
2. ✅ **No processing needed** - collections are pre-built
3. ✅ **Simplest deployment** - just clone and run
4. ✅ **Easy to demo** - works immediately
5. ✅ **Version controlled** - everything in one place

**Command sequence**:
```bash
# 1. Push to GitHub
git add .
git commit -m "Complete house finance application"
git push origin main

# 2. Deploy on server
git clone https://github.com/yourusername/house-finance.git
cd house-finance
./deploy.sh local

# 3. Access
# API: http://your-server:8000
# Interface: http://your-server:8081/budget_test_interface.html
```

This gives you a working system in under 5 minutes! 🚀

## 🔧 Custom Port Configuration

If you need to use different ports, you can customize:

### Manual Port Selection:
```bash
# API server (default 8000)
python src/run_api.py --port 8002

# Test interface (default 8081)
python src/tests/test_server.py --port 8082
```

### Docker with custom ports:
```bash
docker run -d -p 8002:8000 -p 8082:8080 yourusername/house-finance:latest
``` 