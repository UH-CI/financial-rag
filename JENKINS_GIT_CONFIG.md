# Jenkins Git Configuration Fix

## Problem
Jenkins is failing to clone the repository due to slow network speeds and connection drops:
- Repository size: ~261 MB
- Network speed: ~400 KB/s
- Error: `fetch-pack: unexpected disconnect while reading sideband packet`

## Solution 1: Shallow Clone (✅ Implemented in Jenkinsfile)

The Jenkinsfile now uses shallow clone with `depth: 1`, which:
- Only clones the latest commit (not full history)
- Reduces clone size from ~260MB to ~5-10MB
- Speeds up checkout by 20-30x

## Solution 2: Configure Git on Jenkins Server

If shallow clone isn't enough, SSH into Jenkins server and run:

```bash
# SSH into Jenkins server
ssh user@jenkins-server

# Switch to Jenkins user
sudo su - jenkins

# Configure Git for better network handling
git config --global http.postBuffer 524288000       # 500MB buffer
git config --global http.lowSpeedLimit 1000         # Min 1KB/s
git config --global http.lowSpeedTime 600           # Wait 10 min before timeout
git config --global pack.windowMemory 256m          # Use more memory for packing
git config --global pack.packSizeLimit 256m         # Limit pack size
git config --global core.compression 0              # Disable compression (faster)

# For SSH connections (if using git@github.com)
cat >> ~/.ssh/config << 'EOF'
Host github.com
    ServerAliveInterval 60
    ServerAliveCountMax 30
    TCPKeepAlive yes
    IPQoS throughput
EOF

# Verify configuration
git config --global --list
```

## Solution 3: Use HTTPS Instead of SSH

If SSH is slow, try HTTPS:

1. In Jenkins, update the repository URL:
   - From: `git@github.com:UH-CI/financial-rag.git`
   - To: `https://github.com/UH-CI/financial-rag.git`

2. Update credentials to use GitHub Personal Access Token instead of SSH key

## Solution 4: Check Network Issues

```bash
# Test GitHub connectivity
ssh -T git@github.com

# Test download speed
curl -o /dev/null https://github.com/UH-CI/financial-rag/archive/refs/heads/main.zip

# Check if VPN/firewall is throttling
traceroute github.com
```

## Solution 5: Use Git LFS (Long-term)

If the repository has large files:

```bash
# Check for large files
git rev-list --objects --all | \
  git cat-file --batch-check='%(objecttype) %(objectname) %(objectsize) %(rest)' | \
  awk '/^blob/ {print substr($0,6)}' | \
  sort --numeric-sort --key=2 | \
  tail -20

# If large files found, consider using Git LFS
git lfs migrate import --include="*.json,*.db" --everything
```

## Monitoring

After applying fixes, monitor:
- Clone time should drop from 10+ minutes to < 1 minute
- Network errors should disappear
- Build success rate should improve

## Current Status

✅ **Shallow clone implemented** - Should fix the issue
⏳ **Waiting for next build** to verify
📊 **Expected improvement**: 20-30x faster checkout
