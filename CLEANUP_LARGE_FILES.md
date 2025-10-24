# Clean Up Large Files from Git History

## Problem
The repository is **375 MB** due to large files committed in the past:
- `src/bill_data/document_vectors.json` - 570 MB
- `src/chroma_db/data/chroma.sqlite3` - 468 MB  
- `src/bill_data/introduction_document_vectors.json` - 323 MB
- Various ChromaDB and JSON files

These files are **already in `.gitignore`** but remain in Git history.

## Impact
- Slow clones (10+ minutes on Jenkins)
- Wasted bandwidth
- Large repository size

## Solution: Remove from Git History

### ⚠️ WARNING
This rewrites Git history. **All team members must re-clone** after this operation.

### Step 1: Backup (Optional but Recommended)
```bash
cd /Users/rodericktabalba/Documents/GitHub/financial-rag
git clone . ../financial-rag-backup
```

### Step 2: Install BFG Repo-Cleaner (Faster than git-filter-branch)
```bash
# On macOS
brew install bfg

# Or download manually
# wget https://repo1.maven.org/maven2/com/madgag/bfg/1.14.0/bfg-1.14.0.jar
```

### Step 3: Clean Large Files
```bash
cd /Users/rodericktabalba/Documents/GitHub/financial-rag

# Remove files larger than 10MB from history
bfg --strip-blobs-bigger-than 10M

# Or remove specific files/folders
bfg --delete-files "*.sqlite3"
bfg --delete-files "document_vectors.json"
bfg --delete-files "introduction_document_vectors.json"
bfg --delete-folders "chroma_db"
bfg --delete-folders "chroma_db_old"

# Clean up the repository
git reflog expire --expire=now --all
git gc --prune=now --aggressive

# Check new size
git count-objects -vH
```

### Step 4: Force Push (⚠️ Coordinate with team!)
```bash
# Push the cleaned history
git push origin --force --all
git push origin --force --tags
```

### Step 5: Team Members Must Re-clone
Everyone on the team needs to:
```bash
# Delete old clone
rm -rf financial-rag

# Re-clone fresh
git clone git@github.com:UH-CI/financial-rag.git
cd financial-rag
npm install  # Reinstall hooks
```

## Alternative: Shallow Clone (No History Rewrite)

If you don't want to rewrite history, use shallow clone in Jenkinsfile:
```groovy
[$class: 'CloneOption', timeout: 30, depth: 1, shallow: true]
```

This only downloads the latest commit (~10-20 MB instead of 375 MB).

## Expected Results

### Before Cleanup
- Repository size: **375 MB**
- Clone time: **10+ minutes**
- Objects: **3839**

### After Cleanup
- Repository size: **~20-30 MB** (estimated)
- Clone time: **< 1 minute**
- Objects: **~500-800** (estimated)

## Files to Keep Ignored

Make sure these stay in `.gitignore`:
```
# Database files
*.sqlite3
*.db
chroma_db/
src/chroma_db/

# Large vector files
/src/bill_data/document_vectors.json
/src/bill_data/introduction_document_vectors.json

# Extracted/chunked data
/src/documents/storage_documents/*
/src/documents/extracted_text/*
/src/documents/chunked_text/*
```

## Prevention

To prevent this in the future:
1. ✅ Keep `.gitignore` updated
2. ✅ Use pre-commit hooks to block large files
3. ✅ Store large files in S3/external storage
4. ✅ Use Git LFS for necessary large files

## Recommendation

**Option A: Clean history** (Best long-term)
- Requires team coordination
- Permanent fix
- Smaller repo forever

**Option B: Use shallow clone** (Quick fix)
- No coordination needed
- Already implemented in Jenkinsfile
- Doesn't fix root cause

Choose based on your team's availability and coordination ability.
