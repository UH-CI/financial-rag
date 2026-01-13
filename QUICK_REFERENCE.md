# Financial RAG System - Quick Reference Guide

**Production**: https://finbot.its.hawaii.edu  
**Documentation**: See `SYSTEM_DOCUMENTATION.md`

---

## 🚀 Quick Start

### Development
```bash
git clone https://github.com/UH-CI/financial-rag.git
cd financial-rag
cp .env.example .env
cp src/.env.example src/.env
cp frontend/.env.example frontend/.env
# Edit .env files with your credentials
./GO.sh development
```

**Access**: http://localhost:3000

### Production Deployment
```bash
# SSH to server
ssh exouser@<jetstream2-server>
cd /home/exouser/RAG-system

# Deploy
./GO.sh prod --deploy --workers 8
```

---

## 🏗️ Architecture at a Glance

```
React Frontend → FastAPI Backend → ChromaDB (Vector Store)
                      ↓               Redis (Queue)
                Google Gemini         SQLite (Users)
                Selenium Grid
                  Auth0
```

**Infrastructure**: Jetstream2 (16 CPUs, 60GB RAM, 60GB storage)

---

## 🎯 Core Features

| Feature | Purpose | Key Tech |
|---------|---------|----------|
| **Fiscal Note Generation** | Auto-generate fiscal impact reports | Selenium + Gemini LLM |
| **RefBot** | AI committee assignment | Gemini (0.89 precision on PBS) |
| **Similar Bill Search** | Find related legislation | Gemini + TF-IDF embeddings |
| **HRS Search** | Search Hawaii Revised Statutes | Web scraping + RAG |
| **User Management** | Role-based access control | Auth0 + SQLite |

---

## ⚙️ Key Commands

### GO.sh Script
```bash
./GO.sh dev                  # Start development
./GO.sh dev --workers 4      # Dev with 4 workers
./GO.sh dev --build          # Rebuild containers
./GO.sh dev --logs           # View logs
./GO.sh --down               # Stop all services
./GO.sh prod --deploy        # Full production deployment
./GO.sh --backup             # Backup fiscal notes
```

### Docker
```bash
docker compose ps                    # Status
docker compose logs api              # API logs
docker compose logs worker           # Worker logs
docker compose exec api bash         # Shell into API
docker compose restart worker        # Restart worker
```

### Database
```bash
sqlite3 src/database/users.db
SELECT * FROM users;
SELECT * FROM users WHERE is_admin = 1;
```

### Redis Queue
```bash
docker exec -it redis-server redis-cli
LLEN rq:queue:default       # Queue length
LRANGE rq:queue:default 0 -1  # View queue
```

---

## 🔐 Environment Variables

**Required** (in `src/.env`):
- `GOOGLE_API_KEY` - Gemini API key
- `AUTH0_DOMAIN` - Auth0 domain
- `AUTH0_AUDIENCE` - Auth0 API audience

**Optional**:
- `WORKERS` - Number of API workers (default: 1)
- `LOG_LEVEL` - Logging level (default: debug)
- `SLACK_WEBHOOK_URL` - Deployment notifications

---

## 👥 User Roles

1. **Super Admin**
   - Full system access
   - Can create admins
   - Assign any permissions

2. **Admin**
   - User management
   - Can only assign their own permissions
   - Cannot create other admins

3. **Basic User**
   - Feature access only:
     - fiscalNoteGeneration
     - similarBillSearch
     - hrsSearch
     - refBot
---

## 📈 Production Monitoring

- **Microsoft Clarity**: Session recording and heatmaps
- **Health Check**: GET https://finbot.its.hawaii.edu/health
- **API Docs**: GET https://finbot.its.hawaii.edu/docs

---

## 🔄 CI/CD (Jenkins)

**Trigger**: Push to `main` branch

**Pipeline**:
1. Checkout
2. Check for changes
3. Backup fiscal notes
4. Update code
5. Build frontend
6. Deploy with GO.sh
7. Slack notification

---

## 📚 Key Files

| File | Purpose |
|------|---------|
| `GO.sh` | Unified deployment script |
| `Jenkinsfile` | CI/CD pipeline |
| `src/main.py` | Main API server (3,419 lines) |
| `src/fiscal_notes/generation/` | Fiscal note pipeline steps |
| `src/refbot/` | Committee assignment module |
| `src/database/users.db` | User database |
| `frontend/` | React TypeScript frontend |

---

## 🔗 Important URLs

- **Production**: https://finbot.its.hawaii.edu
- **API Docs**: https://finbot.its.hawaii.edu/docs
- **Capitol Bills**: https://www.capitol.hawaii.gov/
- **HRS Database**: https://www.capitol.hawaii.gov/hrscurrent/

---

## 📞 Support

**Documentation**: `SYSTEM_DOCUMENTATION.md` (Full details)  
**Questions**: See "Remaining Questions" section in main docs

---

**Last Updated**: January 12, 2026  
**Version**: 1.0
