# Contributing to Financial RAG

## Development Setup

### Prerequisites
- Node.js 18+ (for frontend)
- Python 3.9+ (for backend)
- Git

### Initial Setup

1. **Clone the repository**
   ```bash
   git clone https://github.com/UH-CI/financial-rag.git
   cd financial-rag
   ```

2. **Install root dependencies (Git hooks)**
   ```bash
   npm install
   ```
   This will automatically set up Git hooks using Husky.

3. **Install frontend dependencies**
   ```bash
   cd frontend
   npm install
   ```

4. **Install backend dependencies**
   ```bash
   cd src
   pip install -r requirements.txt
   ```

## Git Workflow

### Pre-Push Checks

When pushing to the `main` branch, the following checks run automatically:

1. ✅ **Frontend Build** - Ensures TypeScript compiles and Vite builds successfully
2. ✅ **Frontend Tests** - Runs all unit tests (25 tests)

If any check fails, the push is aborted. Fix the issues before pushing again.

### Bypassing Pre-Push Checks (Emergency Only)

```bash
git push --no-verify
```

⚠️ **Warning:** Only use in emergencies. Jenkins will still run these checks.

## Testing

### Frontend Tests

```bash
cd frontend

# Run tests once
npm run test:run

# Run tests in watch mode (during development)
npm test

# Run tests with coverage
npm run test:coverage
```

### Test Structure
- **Unit tests**: `src/**/*.test.ts`, `src/**/*.test.tsx`
- **Test utilities**: `src/test/`
- **Mock data**: `src/test/mockData.ts`
- **Test setup**: `src/test/setup.ts`

## Building

### Frontend Build

```bash
cd frontend
npm run build
```

Build output goes to `frontend/dist/`

### Production Build

The Jenkins CI/CD pipeline automatically builds and deploys to production when pushing to `main`.

## Code Quality

### Linting

```bash
cd frontend
npm run lint
```

### TypeScript Type Checking

```bash
cd frontend
npm run type-check  # or just run build
```

## Deployment

### Automatic Deployment (Recommended)

Push to `main` branch triggers Jenkins CI/CD:
1. Checkout code
2. Check for changes
3. Build frontend
4. Deploy to production server
5. Send Slack notification

### Manual Deployment

```bash
# SSH into production server
ssh user@production-server

# Navigate to project
cd /path/to/financial-rag

# Pull latest changes
git pull origin main

# Restart services
./stop_production.sh
./start_production.sh
```

## Troubleshooting

See [JENKINS_TROUBLESHOOTING.md](./JENKINS_TROUBLESHOOTING.md) for common issues and solutions.

### Common Issues

**Build fails locally but passes in CI**
- Clear node_modules: `rm -rf node_modules && npm install`
- Clear build cache: `rm -rf frontend/dist`

**Tests fail locally**
- Clear test cache: `cd frontend && npm run test:run -- --clearCache`
- Check Node version: `node --version` (should be 18+)

**Git hooks not running**
- Reinstall hooks: `npm run prepare`
- Check hook permissions: `chmod +x .husky/pre-push`

## Project Structure

```
financial-rag/
├── frontend/              # React + TypeScript frontend
│   ├── src/
│   │   ├── components/   # React components
│   │   ├── test/         # Test utilities and mock data
│   │   ├── utils/        # Utility functions
│   │   └── services/     # API services
│   ├── dist/             # Build output (gitignored)
│   └── package.json
├── src/                  # Python backend
│   ├── *.py             # Backend modules
│   └── requirements.txt
├── .husky/              # Git hooks
├── Jenkinsfile          # CI/CD pipeline
└── package.json         # Root package (for Git hooks)
```

## Getting Help

- Check [JENKINS_TROUBLESHOOTING.md](./JENKINS_TROUBLESHOOTING.md)
- Check [README.md](./README.md)
- Review Git hooks: `.husky/README.md`
- Contact the team via Slack

## Pull Request Guidelines

1. Create a feature branch from `main`
2. Make your changes
3. Ensure all tests pass locally
4. Ensure build succeeds locally
5. Push to your branch
6. Create a Pull Request
7. Wait for CI/CD checks to pass
8. Request review from team members

## Code Style

- **Frontend**: Follow existing TypeScript/React patterns
- **Backend**: Follow PEP 8 Python style guide
- **Commits**: Use clear, descriptive commit messages
- **Tests**: Write tests for new features
