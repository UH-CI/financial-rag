# Jenkins Troubleshooting Guide

## Git Timeout Issues

### Symptom
```
ERROR: Timeout after 10 minutes
ERROR: Error cloning remote repo 'origin'
hudson.plugins.git.GitException: Command "git fetch --tags --force --progress"
```

### Root Causes
1. **Slow network connection** between Jenkins server and GitHub
2. **Large repository size** taking too long to clone
3. **SSH authentication delays**
4. **Network firewall/VPN issues**
5. **GitHub rate limiting or service issues**

### Solutions Applied

#### 1. Increased Git Timeout (✅ Implemented)
- Changed from default 10 minutes to 30 minutes
- Added custom checkout with extended timeout in Jenkinsfile
- Location: `Jenkinsfile` lines 4-8, 19-34

#### 2. Alternative Solutions (if timeout persists)

**Option A: Use Shallow Clone**
```groovy
[$class: 'CloneOption', timeout: 30, depth: 1, noTags: true, shallow: true]
```
- Only clones recent history
- Faster but loses full git history

**Option B: Use HTTPS instead of SSH**
- Change GitHub URL from `git@github.com:` to `https://github.com/`
- May be faster depending on network configuration

**Option C: Check Jenkins Server Network**
```bash
# SSH into Jenkins server
ssh user@jenkins-server

# Test GitHub connectivity
ssh -T git@github.com

# Check network speed
curl -o /dev/null https://github.com/UH-CI/financial-rag/archive/refs/heads/main.zip
```

**Option D: Configure Git on Jenkins Server**
```bash
# Increase Git buffer size
git config --global http.postBuffer 524288000
git config --global http.lowSpeedLimit 0
git config --global http.lowSpeedTime 999999
```

## Build Failure Notifications

### Enhanced Slack Notifications (✅ Implemented)
The Jenkinsfile now sends detailed failure notifications including:
- Failed stage name
- Last 50 lines of console output
- Direct links to build and console logs

### Location
`Jenkinsfile` lines 121-182

## Common Build Issues

### TypeScript Errors
**Symptom:** `error TS2304: Cannot find name 'global'`
**Solution:** Use `window` instead of `global` in browser environments
**Fixed in:** `frontend/src/test/setup.ts`

### Test Files in Production Build
**Symptom:** Test files being type-checked during production build
**Solution:** Exclude test files in `tsconfig.app.json`
**Fixed in:** `frontend/tsconfig.app.json` line 26

### Index Out of Bounds
**Symptom:** Crash when switching between bills with different fiscal note counts
**Solution:** Reset `selectedNoteIndex` to 0 when loading new bill data
**Fixed in:** `frontend/src/components/FiscalNoteViewer.tsx` line 76

## Monitoring

### Check Build Status
```bash
# Via Jenkins CLI (if configured)
java -jar jenkins-cli.jar -s http://jenkins-server/ get-job financial-rag

# Via Slack
# Notifications are automatically sent on success/failure
```

### Debug Build Locally
```bash
cd frontend
npm run build  # Should complete in < 5 seconds
npm run test:run  # Should pass all tests
```

## Contact
If issues persist, check:
1. Jenkins server logs: `/var/log/jenkins/jenkins.log`
2. GitHub status: https://www.githubstatus.com/
3. Network connectivity between Jenkins and GitHub
