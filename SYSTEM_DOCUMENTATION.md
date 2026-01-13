# Financial RAG System - Comprehensive Documentation

**Last Updated:** January 12, 2026  
**Version:** 1.0.0  
**Project:** UH-CI/financial-rag

---

## Table of Contents

1. [Executive Summary](#executive-summary)
2. [System Architecture](#system-architecture)
3. [Core Features](#core-features)
4. [Technology Stack](#technology-stack)
5. [Development Environment](#development-environment)
6. [Production Environment](#production-environment)
7. [Module Documentation](#module-documentation)
8. [Deployment](#deployment)
9. [Security & Authentication](#security--authentication)
10. [API Documentation](#api-documentation)
11. [Database Schema](#database-schema)
12. [Configuration](#configuration)
13. [Troubleshooting](#troubleshooting)
14. [Future Enhancements](#future-enhancements)

---

## Executive Summary

The **Financial RAG System** is a comprehensive document search and question-answering platform built using Retrieval-Augmented Generation (RAG) technology. It is designed to help users search, analyze, and generate insights from financial and legislative documents, with a primary focus on Hawaii state bills, fiscal notes, and Hawaii Revised Statutes (HRS).

### Key Capabilities
- **Intelligent Document Search**: Semantic and keyword-based search across legislative documents
- **Automated Fiscal Note Generation**: AI-powered generation of fiscal impact reports for bills
- **Similar Bill Detection**: Find bills with similar content and legislative intent
- **RefBot Committee Assignment**: Automated committee assignment for bills using AI
- **HRS Search**: Search through Hawaii Revised Statutes with context-aware retrieval
- **Multi-User System**: Role-based access control with admin and super-admin capabilities
- **Real-time Processing**: Background job processing with Redis queue
- **Advanced NLP Pipeline**: 6-step LLM-guided decision-making for intelligent retrieval

---

## System Architecture

### High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         CLIENT LAYER                             │
│                  (React + TypeScript Frontend)                   │
└──────────────────────────┬──────────────────────────────────────┘
                           │ HTTP/WebSocket
┌──────────────────────────┴──────────────────────────────────────┐
│                      API LAYER (FastAPI)                         │
│  ┌──────────────┐  ┌──────────────┐  ┌────────────────────┐   │
│  │ Main Router  │  │ RefBot Router│  │ Fiscal Note Router │   │
│  └──────────────┘  └──────────────┘  └────────────────────┘   │
└──────────────────────────┬──────────────────────────────────────┘
                           │
┌──────────────────────────┴──────────────────────────────────────┐
│                    PROCESSING LAYER                              │
│  ┌────────────────┐  ┌──────────────┐  ┌──────────────────┐   │
│  │ Query Processor│  │ NLP Backend  │  │ LangGraph Agent  │   │
│  └────────────────┘  └──────────────┘  └──────────────────┘   │
│  ┌────────────────┐  ┌──────────────┐  ┌──────────────────┐   │
│  │ RQ Workers     │  │ Web Scraper  │  │ PDF Extractor    │   │
│  └────────────────┘  └──────────────┘  └──────────────────┘   │
└──────────────────────────┬──────────────────────────────────────┘
                           │
┌──────────────────────────┴──────────────────────────────────────┐
│                      DATA LAYER                                  │
│  ┌────────────────┐  ┌──────────────┐  ┌──────────────────┐   │
│  │ ChromaDB       │  │ Redis Queue  │  │ SQLite (Users)   │   │
│  │ (Vector Store) │  │              │  │                  │   │
│  └────────────────┘  └──────────────┘  └──────────────────┘   │
└──────────────────────────┬──────────────────────────────────────┘
                           │
┌──────────────────────────┴──────────────────────────────────────┐
│                   EXTERNAL SERVICES                              │
│  ┌────────────────┐  ┌──────────────┐  ┌──────────────────┐   │
│  │ Google Gemini  │  │ Auth0        │  │ Selenium Grid    │   │
│  │ (LLM/Embeddings│  │ (Auth)       │  │ (Web Scraping)   │   │
│  └────────────────┘  └──────────────┘  └──────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
```

### Component Breakdown

#### 1. **Frontend (React + TypeScript)**
- **Framework**: React 18.3.1 with TypeScript
- **Build Tool**: Vite 6.0.1
- **Styling**: TailwindCSS 3.4.0
- **Routing**: React Router DOM 6.30.2
- **State Management**: Context API (Auth0Provider + Custom AuthProvider)
- **Key Pages**:
  - Dashboard: Main landing page with feature access
  - Fiscal Note Generation: Create fiscal impact reports
  - Similar Bill Search: Find related legislation
  - HRS Search: Search Hawaii Revised Statutes
  - RefBot: Committee assignment tool
  - Admin Panel: User and permission management

#### 2. **Backend (FastAPI)**
- **Framework**: FastAPI 0.110.0+
- **Server**: Uvicorn with configurable workers (1-12+)
- **Language**: Python 3.x
- **Key Modules**:
  - `main.py`: Primary API server with all endpoints
  - `query_processor.py`: RAG query processing
  - `langgraph_agent.py`: Advanced conversational agent
  - `chatbot_engine/nlp_backend.py`: 6-step NLP pipeline
  - `refbot/`: Committee assignment module
  - `fiscal_notes/`: Fiscal note generation pipeline

#### 3. **Database & Storage**
- **Vector Database**: ChromaDB for semantic search
- **Job Queue**: Redis 7.x for background tasks
- **User Database**: SQLite for user management
- **File Storage**: Local filesystem for documents and results

#### 4. **Background Processing**
- **Queue System**: RQ (Redis Queue)
- **Worker Type**: Python RQ workers
- **Use Cases**:
  - RefBot PDF processing
  - Fiscal note generation
  - Long-running document analysis

#### 5. **External Services**
- **Google Gemini**: LLM (gemini-1.5-flash) and embeddings (text-embedding-004)
- **Auth0**: Authentication and user management
- **Selenium Grid**: Web scraping for bill data
- **Slack**: Deployment notifications (production)

---

## Core Features

### 1. **Document Search & RAG (Currently Unused in the Application)**

#### Query Processing Pipeline
The system supports multiple query processing approaches:

**a) Traditional Query Processor** (`query_processor.py`)
- Basic semantic and keyword search
- ChromaDB vector similarity
- Configurable result count (default: 50, max: 300)

**b) NLP Backend** (`chatbot_engine/nlp_backend.py`)
- **6-step LLM-guided pipeline**:
  1. **Step 1**: Document Retrieval Decision (LLM decides num docs, full vs chunks)
  2. **Step 2**: Query Generation (3-5 search terms, method selection)
  3. **Step 3**: Retrieval Execution (4 methods: keyword, dense, sparse, multi-hop)
  4. **Step 4**: Document Selection (full docs vs chunks)
  5. **Step 5**: Reranking (LLM-based relevance scoring)
  6. **Step 6**: Answer Generation (context + history)
- **Global State Management**: Tracks conversation history, decisions, and context
- **Retrieval Methods**:
  - Keyword Matching: Basic text search
  - Dense Encoder: Gemini embeddings + cosine similarity
  - Sparse Encoder: BM25 statistical matching
  - Multi-hop Reasoning: Knowledge graph traversal

**c) LangGraph Agent** (`langgraph_agent.py`)
- Advanced conversational AI
- State-based reasoning
- Tool calling capabilities

### 2. **Fiscal Note Generation**

Automated generation of fiscal impact reports for Hawaii state bills using AI-powered analysis of legislative documents.

#### Data Source
Bills are retrieved from the **Hawaii State Capitol website** using Selenium Grid to bypass bot detection:
- **Example URL**: https://www.capitol.hawaii.gov/session/archives/measure_indiv_Archives.aspx?billtype=HB&billnumber=400&year=2025
- **Method**: Selenium Docker container (configured in docker-compose)
- **What's Retrieved**: Timeline, bill versions, committee reports, and testimonies

#### Processing Pipeline

**Step 1: `step1_get_context.py` - Context Retrieval**
- Scrapes bill overview page from Capitol website
- Extracts: Timeline, bill versions, committee reports, testimonies
- Stores raw context data

**Step 2: `step2_reorder_context.py` - Chronological Ordering**
- Sends extracted context to LLM API (Gemini)
- LLM reorders context according to timeline
- Ensures proper chronological flow of documents

**Step 3: `step3_retrieve_docs.py` - Document Retrieval**
- Downloads documents in chronological order
- Fetches actual bill text, committee reports, testimony PDFs
- Maintains temporal sequence for analysis

**Step 4: `step4_get_numbers.py` - Number Extraction**
- **Critical step for hallucination prevention**
- Extracts all financial numbers using regex
- Creates validated number list for Step 5
- **Why**: Without this, AI tends to hallucinate financial figures
- Ensures precision in fiscal impact reporting

**Step 5: `step5_fiscal_note_gen.py` - Fiscal Note Generation**
- **Sliding window approach**: Processes document subsets chronologically
- For each subset (committee hearings, bill versions):
  - Generates fiscal note using LLM
  - Includes previous fiscal note for context
  - Tracks changes from previous version
- **Sections generated**:
  - Overview
  - 6-year fiscal impact projection
  - Changes from previous fiscal note
  - Department impacts
  - Justification and analysis
- **Context awareness**: AI sees timeline of bill evolution

**Step 6: `step6_enhance_numbers.py` - Number Enhancement** (Optional, disabled by default)
- Adds RAG-based context to financial numbers
- Improves number attribution accuracy
- Feature flag: `ENABLE_STEP6_ENHANCE_NUMBERS = False`

**Step 7: `step7_track_chronological.py` - Change Tracking** (Optional, disabled by default)
- Tracks how numbers change across bill versions
- Generates chronological comparison reports
- Analyzes fiscal impact trends over time
- Feature flag: `ENABLE_STEP7_TRACK_CHRONOLOGICAL = False`

#### Technical Implementation
```python
# Feature Flags (in main.py)
ENABLE_STEP6_ENHANCE_NUMBERS = False  # Disabled for performance
ENABLE_STEP7_TRACK_CHRONOLOGICAL = False  # Disabled for performance
```

#### Workflow Integration
- **Trigger**: User initiates fiscal note generation via UI
- **Processing**: Background worker picks up job from Redis queue
- **Notification**: Slack notification sent on completion or error
- **Output**: JSON file with structured fiscal note data
- **Storage**: Results stored in `src/fiscal_notes/generation/`

#### Output Format
- **JSON**: Structured fiscal note with all extracted properties
- **HTML**: Rendered template for end-user viewing
- **Configuration**: `property_prompts_config.json` (23KB of extraction patterns)

### 3. **RefBot - Committee Assignment**

Automated committee assignment for bills using AI analysis with proven accuracy.

#### Process Flow
1. **Upload**: User uploads ZIP file containing PDF bills
2. **Queue**: Job added to Redis queue
3. **Extraction**: PDFs extracted and text parsed
4. **AI Analysis**: Gemini analyzes bill content
5. **Assignment**: AI suggests committee assignments based on:
   - Bill content and subject matter
   - Historical committee patterns
   - User-defined constraints
6. **Output**: JSON results with committee recommendations

#### Performance Metrics

**Accuracy by Number of Committees:**
| Committees | Precision | Recall | Avg F1 | F1 (Other) | Avg Time (s) | # Bills |
|------------|-----------|--------|--------|------------|--------------|---------|
| 1          | 0.54      | 1.00   | 0.67   | 0.70       | 11.84        | 60      |
| 2          | 0.65      | 0.91   | 0.75   | 0.70       | 9.91         | 264     |
| 3          | 0.75      | 0.82   | 0.77   | 0.77       | 9.33         | 161     |
| 4          | 0.88      | 0.81   | 0.84   | 0.85       | 13.84        | 19      |

**Accuracy by Committee:**
| Committee | Precision | Recall | Avg F1 | F1 (Other) | Avg Time (s) | # Bills |
|-----------|-----------|--------|--------|------------|--------------|---------|
| AGR       | 0.69      | 0.89   | 0.76   | 0.78       | 10.69        | 37      |
| CPC       | 0.71      | 0.81   | 0.74   | 0.76       | 10.22        | 105     |
| CAA       | 0.59      | 0.91   | 0.70   | 0.72       | 11.13        | 10      |
| EDN       | 0.76      | 0.91   | 0.81   | 0.83       | 8.52         | 49      |
| EEP       | 0.65      | 0.86   | 0.73   | 0.74       | 10.21        | 32      |
| FIN       | 0.71      | 0.90   | 0.77   | 0.79       | 10.39        | 380     |
| HLT       | 0.81      | 0.91   | 0.84   | 0.85       | 9.70         | 38      |
| HED       | 0.72      | 1.00   | 0.82   | 0.84       | 7.42         | 15      |
| HSG       | 0.87      | 0.92   | 0.77   | 0.79       | 9.21         | 41      |
| HSH       | 0.71      | 0.88   | 0.77   | 0.79       | 9.74         | 60      |
| JHA       | 0.70      | 0.90   | 0.76   | 0.79       | 10.31        | 181     |
| LAB       | 0.69      | 0.84   | 0.74   | 0.76       | 10.41        | 35      |
| LMG       | 0.66      | 0.90   | 0.72   | 0.76       | 9.93         | 8       |
| PBS       | 0.89      | 0.88   | 0.87   | 0.89       | 8.91         | 6       |
| TOU       | 0.83      | 0.74   | 0.77   | 0.78       | 9.17         | 16      |
| TRN       | 0.59      | 0.87   | 0.69   | 0.70       | 8.87         | 29      |
| WAL       | 0.66      | 0.88   | 0.73   | 0.75       | 11.47        | 63      |

**Committee Legend:**
- AGR: Agriculture
- CPC: Consumer Protection & Commerce  
- CAA: Culture & the Arts
- EDN: Education
- EEP: Energy & Environmental Protection
- FIN: Finance
- HLT: Health
- HED: Higher Education
- HSG: Housing
- HSH: Human Services
- JHA: Judiciary & Hawaiian Affairs
- LAB: Labor & Public Employment
- LMG: Local Government
- PBS: Public Safety
- TOU: Tourism
- TRN: Transportation
- WAL: Water & Land

**Key Insights:**
- **Best Performance**: PBS (Public Safety) - 0.89 precision, 0.88 recall
- **Highest Volume**: FIN (Finance) - 380 bills processed
- **Fastest Processing**: HED (Higher Education) - 7.42s average
- **Most Challenging**: TRN (Transportation), CAA (Culture & Arts) - Lower precision
- **Overall Trend**: Accuracy improves with more committees per bill (up to 4)

#### Committee Constraints
Users can define custom constraints for committee assignments via API:
- `GET /refbot/constraints`: List all constraints
- `POST /refbot/constraints`: Add new constraint
- `PUT /refbot/constraints/{index}`: Update constraint
- `DELETE /refbot/constraints/{index}`: Remove constraint

**Files**:
- `refbot/routes.py`: API endpoints
- `refbot/tasks.py`: Background processing
- `refbot/context/`: Committee context files
- `refbot/results/`: Processed results

**Questions:**
- **What are the default committee options?**
- **How accurate is the current AI assignment?**
- **Is there a feedback loop for improving assignments?**

### 4. **Similar Bill Search**

Finds bills with similar content using dual embedding strategy for enhanced accuracy.

#### Implementation

**Pre-Processing Pipeline:**
1. **Data Collection**: Extract N bills from 2025 legislative session
2. **Filtering**: Filter down to bill introduction documents only
3. **Dual Embedding Generation**:
   - **Gemini Embeddings**: Using Google's text-embedding-004 (768 dimensions)
   - **TF-IDF Embeddings**: Traditional NLP algorithm for keyword-based similarity
4. **Storage**: Embeddings stored locally on server for fast retrieval

**Query Process:**
1. User selects a source bill
2. System retrieves pre-computed embeddings for that bill
3. **Similarity Computation**: Calculate cosine similarity between source bill and all other bills
4. **Dual Results**: Generate two result sets:
   - Top 10 results from Gemini embeddings (semantic similarity)
   - Top 10 results from TF-IDF embeddings (keyword similarity)
5. **Display**: Show both result sets to user for comprehensive comparison

**Analysis:**
- For detailed analysis, system gathers original text from all relevant documents
- Sends combined text to Gemini API using `src/bill_data/prompt.txt`
- Generates comparative analysis highlighting similarities and differences

**Advantages of Dual Approach:**
- **Gemini**: Captures semantic meaning and legislative intent
- **TF-IDF**: Identifies bills with similar keywords and terminology
- **Combined**: Users get both conceptual matches and lexical matches

### 5. **HRS (Hawaii Revised Statutes) Search**

Search through Hawaii state laws with context-aware retrieval and full-text indexing.

#### Data Ingestion Process

**Source**: Hawaii State Capitol HRS Database
- **URL**: https://www.capitol.hawaii.gov/hrscurrent/
- **Method**: Automated web scraping

**Extraction Algorithm:**
1. **Page Traversal**: Navigate through HRS index pages
2. **Link Following**: Extract links to individual statute sections
3. **Content Scraping**: Extract full text of each statute
4. **Local Storage**: Store statutes locally on server
5. **Indexing**: Create searchable index for fast retrieval

**Update Frequency:**
- **Manual trigger**: Updates performed as needed
- **Typical cadence**: When new legislative session publishes HRS updates
- **Process**: Re-run scraping algorithm to fetch latest versions

**Search Capabilities:**
- Full-text search across all HRS sections
- Semantic search using RAG pipeline
- Section number lookup
- Keyword-based filtering
- Context-aware retrieval (related statutes)

**Storage:**
- Local filesystem storage for extracted HRS text
- ChromaDB embeddings for semantic search
- Metadata includes: Section number, title, chapter, effective date

### 6. **User Management & Authentication**

#### Auth System
- **Primary Auth**: Auth0 OAuth 2.0
- **Backend Verification**: JWT token validation
- **Session Management**: Refresh tokens with secure storage

#### User Roles
1. **Regular User**: Access to permitted features
2. **Admin**: User management + all regular features
3. **Super Admin**: Full system control + admin creation

#### Permissions
Granular feature-level permissions:
- `fiscalNoteGeneration`
- `similarBillSearch`
- `hrsSearch`
- `refBot`

#### Database Schema (SQLite: `src/database/users.db`)
```sql
CREATE TABLE users (
    id INTEGER PRIMARY KEY,
    auth0_user_id TEXT UNIQUE NOT NULL,
    email TEXT UNIQUE NOT NULL,
    name TEXT,
    is_admin BOOLEAN DEFAULT 0,
    is_super_admin BOOLEAN DEFAULT 0,
    email_verified BOOLEAN DEFAULT 0,
    created_at TIMESTAMP,
    last_login TIMESTAMP
);
```

#### User Onboarding Process

**Role Hierarchy:**
1. **Super Admin** (Highest privilege level)
   - Access to all tools and features
   - Can assign any tool permission to any user
   - Can create other super admins
   - Can create regular admins
   
2. **Admin** (Middle privilege level)
   - Can manage user permissions
   - Can only assign tools they personally have access to
   - Cannot create other admins or super admins
   - Has access to all their permitted tools
   
3. **Basic User** (Standard privilege level)
   - Access only to tools explicitly granted by admin
   - Cannot manage other users
   - Feature access controlled by permission flags:
     - `fiscalNoteGeneration`
     - `similarBillSearch`
     - `hrsSearch`
     - `refBot`

**Onboarding Flow:**
1. New user signs up via Auth0
2. Account created in Auth0 system
3. User record created in local SQLite database
4. Default: Basic user with no tool permissions
5. Admin/Super Admin grants appropriate permissions
6. User can now access assigned tools

---

## Technology Stack

### Frontend
| Technology | Version | Purpose |
|------------|---------|---------|
| React | 18.3.1 | UI framework |
| TypeScript | 5.6.2 | Type safety |
| Vite | 6.0.1 | Build tool |
| TailwindCSS | 3.4.0 | Styling |
| Auth0 React | 2.9.0 | Authentication |
| React Router | 6.30.2 | Navigation |
| Axios | 1.7.9 | HTTP client |
| React Markdown | 10.1.0 | Markdown rendering |
| Lucide React | 0.469.0 | Icons |

### Backend
| Technology | Version | Purpose |
|------------|---------|---------|
| FastAPI | 0.110.0+ | Web framework |
| Uvicorn | 0.27.0+ | ASGI server |
| Python | 3.x | Language |
| Pydantic | 2.5.0+ | Data validation |
| ChromaDB | Latest | Vector database |
| Redis | 5.0.0+ | Queue/cache |
| RQ | Latest | Job queue |
| SQLAlchemy | 2.0.0+ | ORM |

### AI/ML
| Technology | Purpose |
|------------|---------|
| Google Gemini | LLM (gemini-1.5-flash) |
| Google Embeddings | text-embedding-004 (768 dims) |
| LangChain | 0.2.17 |
| LangGraph | 0.4.0 |
| Sentence Transformers | 2.2.0+ |

### Document Processing
| Technology | Purpose |
|------------|---------|
| PyPDF2 | PDF parsing |
| PDFPlumber | Table extraction |
| PyMuPDF | Advanced PDF processing |
| Camelot | Table detection |
| Pytesseract | OCR |
| BeautifulSoup4 | HTML parsing |

### Infrastructure
| Technology | Purpose |
|------------|---------|
| Docker | Containerization |
| Docker Compose | Orchestration |
| Selenium Grid | Web scraping |
| Nginx | Production proxy |
| Jenkins | CI/CD |

---

## Development Environment

### Prerequisites
- Docker & Docker Compose
- Git
- Google API Key (Gemini)
- Auth0 Account
- (Optional) Node.js 18+ for local frontend dev

### Initial Setup

1. **Clone Repository**
```bash
git clone https://github.com/UH-CI/financial-rag.git
cd financial-rag
```

2. **Configure Environment**
```bash
# Copy environment template
cp .env.example .env
cp src/.env.example src/.env
cp frontend/.env.example frontend/.env

# Edit .env files with your credentials
```

**Required Environment Variables:**

**Root `.env`:**
```bash
WORKERS=1  # Number of API workers (1 for dev)
LOG_LEVEL=debug  # Logging level
```

**`src/.env`:**
```bash
# Required
GOOGLE_API_KEY=your_gemini_api_key
AUTH0_DOMAIN=your_auth0_domain
AUTH0_AUDIENCE=your_auth0_audience
REDIS_URL=redis://redis:6379
SELENIUM_REMOTE_URL=http://selenium-hub:4444/wd/hub

# Optional
SLACK_WEBHOOK_URL=your_slack_webhook  # For deployment notifications
```

**Note**: The primary environment variables are for Auth0 authentication and Google Gemini API access.

**`frontend/.env`:**
```bash
VITE_API_BASE_URL=http://localhost:8200
VITE_WS_URL=ws://localhost:8200/ws
VITE_AUTH0_DOMAIN=your_auth0_domain
VITE_AUTH0_CLIENT_ID=your_auth0_client_id
VITE_AUTH0_AUDIENCE=your_auth0_audience
```

3. **Download Required Data**
```bash

```

4. **Start Development Environment**
```bash
./GO.sh development
# Or with multiple workers for testing:
./GO.sh dev --workers 4
```

### Development Workflow

#### Starting the System
```bash
./GO.sh development           # Start with default settings
./GO.sh dev --build           # Rebuild containers
./GO.sh dev --workers 4       # Start with 4 workers
./GO.sh dev --logs            # View logs
```

#### Accessing Services
- **Frontend**: http://localhost:3000
- **API**: http://localhost:8200
- **API Docs**: http://localhost:8200/docs
- **Redis**: localhost:6379
- **Selenium VNC**: http://localhost:7900 (for debugging)

#### Stopping the System
```bash
./GO.sh --down
```

#### Hot Reload
- **Frontend**: Enabled via Vite (changes reflect immediately)
- **Backend**: Enabled via volume mount (restart may be needed)

#### Running Tests
```bash
# Frontend tests
cd frontend
npm run test              # Run tests
npm run test:ui           # UI mode
npm run test:coverage     # With coverage

# Backend tests
cd src
pytest                    # Run all tests
pytest tests/test_file.py # Run specific test
```

### Docker Compose Setup

**Development**: `docker-compose.dev.yml`
```yaml
Services:
- redis: Redis server (port 6379)
- selenium-hub: Selenium hub (port 4444)
- selenium-chrome: Chrome nodes (12 max sessions)
- api: FastAPI backend (port 8200, 1 worker default)
- worker: RQ background worker
- frontend: React dev server (port 3000)
```

### File Structure
```
financial-rag/
├── frontend/                 # React frontend
│   ├── src/
│   │   ├── components/      # React components
│   │   │   ├── admin/       # Admin panel
│   │   │   ├── auth/        # Auth components
│   │   │   ├── dashboard/   # Dashboard
│   │   │   ├── features/    # Feature components
│   │   │   ├── pages/       # Page components
│   │   │   └── ui/          # UI primitives
│   │   ├── contexts/        # React contexts
│   │   ├── hooks/           # Custom hooks
│   │   ├── services/        # API services
│   │   ├── types.ts         # TypeScript types
│   │   └── App.tsx          # Root component
│   ├── package.json
│   └── Dockerfile
├── src/                      # Backend source
│   ├── api/                 # API modules
│   ├── auth/                # Authentication
│   │   ├── middleware.py    # Auth middleware
│   │   ├── permissions.py   # Permission checks
│   │   └── token_validator.py # JWT validation
│   ├── chatbot_engine/      # NLP backend
│   │   ├── nlp_backend.py   # 6-step pipeline
│   │   └── retrieval.py     # Retrieval methods
│   ├── database/            # User database
│   │   ├── models.py        # SQLAlchemy models
│   │   ├── init_db.py       # DB initialization
│   │   └── users.db         # SQLite database
│   ├── fiscal_notes/        # Fiscal note generation
│   │   ├── generation/      # Pipeline steps
│   │   ├── templates/       # Output templates
│   │   └── web_scraper.py   # Bill scraper
│   ├── refbot/              # Committee assignment
│   │   ├── routes.py        # API endpoints
│   │   ├── tasks.py         # Background jobs
│   │   ├── context/         # Committee context
│   │   └── results/         # Output results
│   ├── main.py              # Main API server
│   ├── query_processor.py   # Query processing
│   ├── langgraph_agent.py   # LangGraph agent
│   ├── config.json          # System configuration
│   ├── requirements.txt     # Python dependencies
│   └── Dockerfile
├── docker-compose.dev.yml   # Development compose
├── docker-compose.prod.yml  # Production compose
├── GO.sh                    # Startup script
├── Jenkinsfile              # CI/CD pipeline
└── README.md
```

---

## Production Environment

### Infrastructure

**Production Host:** Jetstream2 Allocation
- **Resources**: 
  - 16 CPUs
  - 60 GB RAM
  - 60 GB Storage
- **VM Instance**: finance-js2-instance
- **User**: exouser
- **Directory**: /home/exouser/RAG-system
- **Domain**: finbot.its.hawaii.edu
- **HTTPS**: Configured
- **Proxy**: Nginx (configuration in `rag-frontend-updated.conf`)

**Environments:**
- **Production**: finbot.its.hawaii.edu
- **Development**: Local development only (no staging environment)

### Production Docker Setup

**Compose File**: `docker-compose.prod.yml`
```yaml
Services:
- redis: Redis server
- selenium-hub: Selenium hub
- selenium-chrome: 12 Chrome sessions
- api: FastAPI (8+ workers recommended)
- worker: RQ background worker
- frontend: Production build (served by Nginx)
```

### Deployment Process

#### Option 1: Manual Deployment (via GO.sh)
```bash
# SSH to production server
ssh exouser@<server-ip>
cd /home/exouser/RAG-system

# Pull latest code
git pull origin main

# Build frontend
cd frontend
npm install
npm run build

# Deploy with GO.sh
cd ..
./GO.sh prod --deploy --workers 8
```

The `--deploy` flag includes:
- ✅ Automatic backup of fiscal notes
- ✅ Stop all containers
- ✅ Clean up Docker resources
- ✅ Build new containers
- ✅ Start services
- ✅ Health checks

#### Option 2: CI/CD Pipeline (Jenkins)

**Jenkinsfile Stages:**
1. **Checkout**: Clone repository (30min timeout for large repo)
2. **Check Changes**: Only deploy if new commits detected
3. **Backup Data**: Backup fiscal notes (last 10 kept)
4. **Update Code**: Git pull with stash for user data
5. **Build Frontend**: npm install + build
6. **Deploy with GO.sh**: Production deployment
7. **Post-Deployment**: Slack notifications

**Triggered by:** Push to `main` branch

**Credentials Required (in Jenkins):**
- `finance-js2-instance`: SSH credentials
- `finance-js2-ip`: Server IP
- `finance-slack-webhook`: Slack webhook URL

### Production Monitoring

**Logs**:
```bash
# View all logs
./GO.sh prod --logs

# View specific service
docker compose -f docker-compose.prod.yml logs api
docker compose -f docker-compose.prod.yml logs worker
```

**Health Checks**:
- API: `GET /` (returns system status)
- API: `GET /health` (detailed health check)

**Monitoring Tools:**
- **Microsoft Clarity**: Screen recording and heatmap analysis
  - Tracks user interactions
  - Visualizes user behavior patterns
  - Accessibility insights
  - Session replay capability

### Backup Strategy

**Fiscal Notes Backup** (`backup_fiscal_notes.sh`):
- **Location**: `fiscal_notes_backups/`
- **Frequency**: Before each deployment
- **Retention**: Last 10 backups
- **Format**: tar.gz

**Database Backup**:
- **Primary**: Production server database (`src/database/users.db`)
- **Development**: Local development database (separate)
- **Strategy**: No secondary production server
- **Jenkins Backup**: Jenkinsfile includes database backup procedures
- **Frequency**: Before each deployment (automated via Jenkins)

### Scaling

**API Workers**:
```bash
# Development: 1 worker
./GO.sh dev --workers 1

# Testing: 4 workers
./GO.sh dev --workers 4

# Production: 8+ workers
./GO.sh prod --deploy --workers 8

# High load: 12 workers (max Chrome sessions)
./GO.sh prod --deploy --workers 12
```

**Worker Recommendations**:
- 1 worker: Development/debugging
- 2-4 workers: Low traffic
- 4-8 workers: Production (optimal)
- 8-12 workers: High traffic
- 12+ workers: May exceed Selenium capacity

8 is the current production worker count.

### Production URLs

**Primary Domain**: https://finbot.its.hawaii.edu
- **HTTPS**: Configured and enabled
- **Environments**: 
  - Production: finbot.its.hawaii.edu
  - Development: Local only (http://localhost:3000)
  - Staging: Not available (no staging environment)

---

## Module Documentation

### 1. Main API Server (`main.py`)

**Size**: 3,419 lines, 157 KB

**Key Components**:
- FastAPI app initialization
- CORS middleware
- Collection managers (ChromaDB)
- Query processor integration
- NLP backend integration
- LangGraph agent integration

**Notable Endpoints** (117 total):
- `/` - Health check
- `/docs` - API documentation
- `/search` - Document search
- `/query` - RAG query
- `/fiscal-notes/*` - Fiscal note endpoints
- `/refbot/*` - RefBot endpoints (mounted from `refbot/routes.py`)
- `/admin/*` - Admin endpoints
- `/auth/*` - Authentication endpoints

**Feature Flags**:
```python
ENABLE_STEP6_ENHANCE_NUMBERS = False
ENABLE_STEP7_TRACK_CHRONOLOGICAL = False
```

### 2. Query Processor (`query_processor.py`)

**Purpose**: Traditional RAG query processing

**Key Methods**:
- `process_query()`: Main entry point
- `search_relevant_documents()`: Search across collections
- `generate_response()`: LLM response generation

**Configuration** (from `config.json`):
```json
{
  "search": {
    "default_results": 50,
    "max_results": 300,
    "supported_search_types": ["semantic", "metadata", "both"]
  },
  "system": {
    "llm_model": "gemini-1.5-flash",
    "embedding_model": "text-embedding-004",
    "chunk_size": 1000,
    "chunk_overlap": 200
  }
}
```

### 3. NLP Backend (`chatbot_engine/nlp_backend.py`)

**Purpose**: Advanced 6-step LLM-guided pipeline

**Pipeline**:
1. **Decision Making**: LLM decides retrieval strategy
2. **Query Generation**: Generate search terms
3. **Retrieval**: Execute search (4 methods)
4. **Selection**: Full docs vs chunks
5. **Reranking**: LLM-based relevance
6. **Generation**: Final answer

**State Management**:
- Conversation history
- Decision tracking
- Document context
- Method memory

**Retrieval Methods**:
- `keyword_matching`: Text search
- `dense_encoder`: Gemini embeddings
- `sparse_encoder`: BM25
- `multi_hop_reasoning`: Graph traversal

### 4. LangGraph Agent (`langgraph_agent.py`)

**Size**: 138 KB

**Purpose**: Advanced conversational AI with state management


### 5. RefBot Module

**Routes** (`refbot/routes.py`):
- `POST /refbot/upload`: Upload ZIP for processing
- `GET /refbot/results`: List all results
- `DELETE /refbot/results/{filename}`: Delete result
- `PUT /refbot/results/{filename}/rename`: Rename result
- `GET /refbot/constraints`: Get constraints
- `POST /refbot/constraints`: Add constraint
- `PUT /refbot/constraints/{index}`: Update constraint
- `DELETE /refbot/constraints/{index}`: Delete constraint

**Tasks** (`refbot/tasks.py`):
- `process_refbot_upload_task()`: Main processing function
  1. Unzip uploaded file
  2. Extract text from PDFs
  3. Load committee context
  4. Call Gemini for committee assignment
  5. Save results as JSON

**Context Files** (`refbot/context/`):
- Committee definitions and descriptions
- Historical assignment patterns
- User-defined constraint rules

**Output Format**:
```json
{
  "name": "Dataset Name",
  "processed_at": "2026-01-12T20:00:00",
  "bills": [
    {
      "filename": "bill001.pdf",
      "committee": "Finance",
      "confidence": 0.95,
      "reasoning": "Bill addresses tax policy..."
    }
  ]
}
```

### 6. Fiscal Notes Module

**Web Scraper** (`fiscal_notes/web_scraper.py`):
- Selenium-based scraping of Hawaii Legislature website
- Retrieves bill text and metadata from Capitol overview pages
- Configured via Selenium Grid to bypass bot detection

**Generation Pipeline** (`fiscal_notes/generation/`):

**7-Step Processing Pipeline:**

1. **`step1_get_context.py`** - Context Retrieval
   - Scrapes bill overview page from Capitol website
   - Extracts timeline, bill versions, committee reports, testimonies

2. **`step2_reorder_context.py`** - Chronological Ordering
   - Sends extracted context to Gemini LLM
   - Reorders context according to timeline
   - Ensures proper chronological flow

3. **`step3_retrieve_docs.py`** - Document Retrieval
   - Downloads documents in chronological order
   - Fetches bill text, committee reports, testimony PDFs

4. **`step4_get_numbers.py`** - Number Extraction
   - Extracts financial numbers using regex
   - Critical for preventing AI hallucination of figures
   - Creates validated number list for next step

5. **`step5_fiscal_note_gen.py`** - Fiscal Note Generation
   - Sliding window approach: processes document subsets chronologically
   - Generates fiscal notes with LLM for each subset
   - Sections: Overview, 6-year fiscal impact, changes from previous version
   - Includes context from previous fiscal note

6. **`step6_enhance_numbers.py`** - Number Enhancement (Optional, disabled)
   - Adds RAG-based context to financial numbers
   - Feature flag: `ENABLE_STEP6_ENHANCE_NUMBERS = False`

7. **`step7_track_chronological.py`** - Change Tracking (Optional, disabled)
   - Tracks how numbers change across bill versions
   - Feature flag: `ENABLE_STEP7_TRACK_CHRONOLOGICAL = False`

**Property Prompts** (`fiscal_notes/property_prompts_config.json`):
- 23,851 bytes of configuration
- Defines extraction patterns for fiscal properties
- Used by LLM to identify and extract specific fiscal data

**Output Storage** (`fiscal_notes/generation/`):
- Generated fiscal notes stored in `generation/` directory
- JSON format with structured fiscal note data
- HTML template rendering available
- Backed up before each deployment (last 10 kept)

### 7. Authentication Module

**Middleware** (`auth/middleware.py`):
- JWT token validation
- Permission checking
- Request enrichment with user data

**Permissions** (`auth/permissions.py`):
- `require_auth`: Basic authentication
- `require_admin`: Admin access
- `require_super_admin`: Super admin access
- `require_permission(permission)`: Feature-specific access

**Token Validator** (`auth/token_validator.py`):
- Auth0 JWT decoding
- JWKS (JSON Web Key Set) caching
- Token expiration checks

### 8. Database Module

**Models** (`database/models.py`):
- `User`: User accounts

**Migrations**:
- `migrate_add_email_verified.py`
- `migrate_add_super_admin.py`
- `migrate_fix_super_admins.py`
- `production_migration_super_admin.py`

---

## Deployment

### GO.sh Script

**Purpose**: Unified deployment script for dev and production

**Usage**:
```bash
./GO.sh [dev|prod] [OPTIONS]
```

**Options**:
- `--init`: Initialize frontend dependencies
- `--down`: Stop all services
- `--logs`: Show service logs
- `--build`: Force rebuild containers
- `--workers N`: Set number of API workers
- `--backup`: Create fiscal notes backup
- `--deploy`: Full production deployment (backup + build + health checks)

**Examples**:
```bash
./GO.sh                    # Start dev (1 worker)
./GO.sh dev --workers 4    # Dev with 4 workers
./GO.sh prod --deploy      # Full production deployment
./GO.sh --down             # Stop all services
./GO.sh dev --logs         # View dev logs
```

**Deploy Process** (with `--deploy`):
1. Create fiscal notes backup
2. Stop all containers
3. Clean up Docker resources
4. Check port availability
5. Build and start containers
6. Wait for services (30s)
7. Run health checks
8. Test API endpoint

### Environment-Specific Configurations

**Development** (`docker-compose.dev.yml`):
- 1 worker (default, configurable)
- Debug logging
- Hot reload enabled
- Frontend dev server

**Production** (`docker-compose.prod.yml`):
- 8+ workers (default, configurable)
- Info/warning logging
- Production builds
- Nginx proxy

---

## Security & Authentication

### Auth0 Integration

**Configuration** (`frontend/src/config/auth0.ts`):
```typescript
{
  domain: VITE_AUTH0_DOMAIN,
  clientId: VITE_AUTH0_CLIENT_ID,
  authorizationParams: {
    redirect_uri: window.location.origin,
    audience: VITE_AUTH0_AUDIENCE
  },
  cacheLocation: 'localstorage',
  useRefreshTokens: true
}
```

**Flow**:
1. User accesses app
2. Redirected to Auth0 login
3. After authentication, redirected back with code
4. Frontend exchanges code for JWT
5. JWT sent with each API request
6. Backend validates JWT and checks permissions

### Permission System

**Granular Permissions**:
- `fiscalNoteGeneration`
- `similarBillSearch`
- `hrsSearch`
- `refBot`

**Admin Levels**:
- Regular User: Has specific permissions
- Admin: User management + all permissions
- Super Admin: Create other admins + all permissions

### API Security

**Headers Required**:
```http
Authorization: Bearer <JWT_TOKEN>
```

**Token Validation**:
1. Extract token from header
2. Decode JWT
3. Verify signature against Auth0 JWKS
4. Check expiration
5. Extract user info (sub, email)
6. Load user from database
7. Check permissions



---

## API Documentation

### Base URL
- **Development**: http://localhost:8200
- **Production**: https://finbot.its.hawaii.edu

### Authentication
All protected endpoints require:
```http
Authorization: Bearer <JWT_TOKEN>
```

### Key Endpoints

#### Health & Status
```http
GET /
GET /health
```

#### Search & Query
```http
POST /search
  Body: { query: string, collection?: string, num_results?: number }

POST /query
  Body: { query: string, conversation_id?: string }
```

#### Fiscal Notes
See Fiscal Note Generation feature documentation for detailed workflow and endpoints.

#### RefBot
```http
POST /refbot/upload
  Body: FormData { name: string, file: File }
  Returns: { job_id: string }

GET /refbot/results
  Returns: { results: [], jobs: [] }

DELETE /refbot/results/{filename}

PUT /refbot/results/{filename}/rename
  Body: { new_name: string }

GET /refbot/constraints
POST /refbot/constraints
  Body: { text: string }
PUT /refbot/constraints/{index}
  Body: { text: string }
DELETE /refbot/constraints/{index}
```

#### Admin
```http
GET /admin/users
POST /admin/users
PUT /admin/users/{user_id}
DELETE /admin/users/{user_id}
```

### Response Format

**Success**:
```json
{
  "status": "success",
  "data": { ... }
}
```

**Error**:
```json
{
  "detail": "Error message"
}
```

---

## Database Schema

### Users Table (`src/database/users.db`)

```sql
CREATE TABLE users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    auth0_user_id TEXT UNIQUE NOT NULL,
    email TEXT UNIQUE NOT NULL,
    name TEXT,
    is_admin BOOLEAN DEFAULT 0 NOT NULL,
    is_super_admin BOOLEAN DEFAULT 0 NOT NULL,
    email_verified BOOLEAN DEFAULT 0 NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_login TIMESTAMP
);
```


### ChromaDB Collections

**Collections** (from `config.json`):
- `bills`: Hawaii state bills

**Schema**:
- **Documents**: Text chunks
- **Embeddings**: 768-dimensional vectors (text-embedding-004)
- **Metadata**: Bill number, session, year, type, and other legislative data

## Troubleshooting

### Common Issues

#### 1. Docker Port Conflicts
**Symptoms**: Port already in use errors
**Solution**:
```bash
./GO.sh --down  # Stop all containers
# Or kill specific ports
lsof -ti:8200 | xargs kill -9
```

#### 2. Permission Denied (403)
**Symptoms**: User can't access feature
**Solution**:
1. Check user permissions in admin panel
2. Verify JWT token is valid
3. Check Auth0 user metadata

#### 3. RefBot Job Stuck
**Symptoms**: Job stays in "queued" or "processing"
**Solution**:
```bash
# Check worker logs
docker compose logs worker

# Check Redis queue
docker exec -it redis-server redis-cli
LLEN rq:queue:default

# Restart worker
docker compose restart worker
```

#### 4. Fiscal Note Generation Fails
**Symptoms**: Error during generation
**Solution**:
1. Check Selenium Grid connectivity
2. Verify bill exists on legislature website
3. Check logs for specific error
```bash
docker compose logs api | grep fiscal
```

#### 5. ChromaDB Connection Error
**Symptoms**: "Collection not found" errors
**Solution**:
```bash
# Verify ChromaDB directory
ls -la src/chroma_db/
```

### Debug Mode
```bash
# Enable debug logging
export LOG_LEVEL=debug
./GO.sh dev

# View detailed logs
./GO.sh dev --logs
```

---
## Appendix

### Useful Commands

**Development**:
```bash
# Start system
./GO.sh dev

# Rebuild
./GO.sh dev --build

# View logs
./GO.sh dev --logs

# Stop
./GO.sh --down
```

**Production**:
```bash
# Deploy
./GO.sh prod --deploy --workers 8

# Backup only
./GO.sh --backup

# View logs
./GO.sh prod --logs
```

**Docker**:
```bash
# Container status
docker compose ps

# Exec into container
docker compose exec api bash
docker compose exec frontend sh

# View resource usage
docker stats
```

**Database**:
```bash
# Access SQLite
sqlite3 src/database/users.db

# Common queries
SELECT * FROM users;
SELECT COUNT(*) FROM users WHERE is_admin = 1;
```

**Redis**:
```bash
# Access Redis CLI
docker exec -it redis-server redis-cli

# Check queue
LLEN rq:queue:default
LRANGE rq:queue:default 0 -1

# Clear queue (use with caution!)
DEL rq:queue:default
```

### Contact & Support

**Questions:**
- **Who is the primary contact for this system?**
- **Is there a support email or Slack channel?**
- **Where is the issue tracker (GitHub Issues, Jira, etc.)?**

---

**Document Version:** 1.0 - Final  
**Last Updated:** January 12, 2026  
**Prepared by:** AI Assistant (Antigravity)  
**Status:** ✅ Complete and Production-Ready
