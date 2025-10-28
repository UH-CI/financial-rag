# Fiscal Notes Dev/Production Separation Guide

## ✅ Problem Solved

**Issue:** Users make annotations to fiscal notes on production. We don't want to overwrite their changes when deploying code updates.

**Solution:** Untrack fiscal notes from Git while preserving them on both dev and production servers.

---

## 🎯 How It Works Now

### **Development Environment:**
- ✅ Fiscal notes exist locally in `src/fiscal_notes/generation/`
- ✅ Changes to fiscal notes are **NOT tracked** by Git
- ✅ You can generate new fiscal notes without affecting production
- ✅ Python scripts (`.py`) and documentation (`.md`) are still tracked

### **Production Environment:**
- ✅ Fiscal notes exist in `src/fiscal_notes/generation/`
- ✅ User annotations are preserved during deployments
- ✅ Git pull won't delete or overwrite fiscal notes
- ✅ Files are protected by git stash during deployment

---

## 📋 What's Tracked vs Ignored

### **Tracked (Synced Between Dev/Production):**
```
✅ src/fiscal_notes/generation/*.py          # Python scripts
✅ src/fiscal_notes/generation/*.md          # Documentation
✅ src/fiscal_notes/generation/README*.md    # README files
✅ frontend/                                 # Frontend code
✅ src/ (except fiscal notes)                # Backend code
```

### **Ignored (Local Only):**
```
❌ src/fiscal_notes/generation/HB_*/        # House Bill data
❌ src/fiscal_notes/generation/SB_*/        # Senate Bill data
❌ src/fiscal_notes/generation/september_archive/  # Archived bills
```

---

## 🔧 Deployment Process

When Jenkins deploys to production:

```bash
# 1. Create timestamped backup
BACKUP_DATE=$(date +%Y%m%d_%H%M%S)
tar -czf "/home/exouser/fiscal_notes_backups/fiscal_notes_${BACKUP_DATE}.tar.gz" src/fiscal_notes/generation/

# 2. Keep only last 10 backups
ls -t fiscal_notes_*.tar.gz | tail -n +11 | xargs -r rm

# 3. Stash local changes (user annotations)
git add src/fiscal_notes/generation/
git stash push -m "Preserve user annotations before pull" src/fiscal_notes/generation/

# 4. Pull code updates
git pull origin main

# 5. Restore local changes (user annotations)
git stash pop

# 6. Build and deploy frontend
cd frontend
npm install
npm run build
nginx reload
```

**Result:** Backup created, code updates deploy, fiscal notes with user annotations are preserved!

---

## 📁 Directory Structure

```
src/fiscal_notes/generation/
├── step1_get_context.py          ✅ Tracked
├── step2_reorder_context.py      ✅ Tracked
├── step3_retrieve_docs.py        ✅ Tracked
├── step4_get_numbers.py          ✅ Tracked
├── step5_fiscal_note_gen.py      ✅ Tracked
├── step6_add_chunk_references.py ✅ Tracked
├── test.py                       ✅ Tracked
├── README_step6.md               ✅ Tracked
│
├── HB_727_2025/                  ❌ Ignored (local only)
│   ├── fiscal_notes/
│   │   ├── HB727.json           # Contains user annotations
│   │   └── HB727_metadata.json
│   ├── documents/
│   └── retrieval_log.json
│
├── HB_728_2025/                  ❌ Ignored (local only)
│   └── ...
│
└── september_archive/            ❌ Ignored (local only)
    └── ...
```

---

## 💾 Backup System

### **Automatic Backups (During Deployment)**

Every time Jenkins deploys, it automatically:
1. Creates a timestamped backup: `fiscal_notes_YYYYMMDD_HHMMSS.tar.gz`
2. Stores it in: `/home/exouser/fiscal_notes_backups/`
3. Keeps the last 10 backups (older ones are deleted)

**Backup location on production:**
```
/home/exouser/fiscal_notes_backups/
├── fiscal_notes_20251027_140000.tar.gz
├── fiscal_notes_20251027_150000.tar.gz
├── fiscal_notes_20251027_160000.tar.gz
└── ... (up to 10 backups)
```

### **Manual Backups**

**Backup from production to local dev:**
```bash
./backup_fiscal_notes.sh
```

This will:
- Connect to production server
- Create a backup of all fiscal notes
- Download to `./fiscal_notes_backups/`
- Show backup size and location

**Restore from backup:**
```bash
# Restore to local dev
./restore_fiscal_notes.sh ./fiscal_notes_backups/fiscal_notes_20251027_152000.tar.gz

# Restore to production (use with caution!)
./restore_fiscal_notes.sh ./fiscal_notes_backups/fiscal_notes_20251027_152000.tar.gz production
```

**View backups on production:**
```bash
ssh exouser@production
ls -lh /home/exouser/fiscal_notes_backups/
```

**Download specific backup:**
```bash
scp exouser@production:/home/exouser/fiscal_notes_backups/fiscal_notes_20251027_152000.tar.gz .
```

---

## 🚀 Workflow Examples

### **Scenario 1: Deploy Code Changes**
```bash
# On dev machine
git add frontend/src/components/FiscalNoteContent.tsx
git commit -m "Update fiscal note viewer"
git push origin main

# Jenkins automatically:
# 1. Stashes production fiscal notes (with user annotations)
# 2. Pulls code updates
# 3. Restores fiscal notes
# 4. Deploys frontend
```

**Result:** ✅ Code updated, user annotations preserved!

---

### **Scenario 2: Generate New Fiscal Notes on Dev**
```bash
# On dev machine
cd src/fiscal_notes/generation
python step5_fiscal_note_gen.py --bill HB1234

# New files created:
# HB_1234_2025/fiscal_notes/HB1234.json
# HB_1234_2025/documents/...

git status
# Shows: nothing to commit (fiscal notes are ignored)
```

**Result:** ✅ New fiscal notes stay on dev, don't affect production!

---

### **Scenario 3: User Makes Annotations on Production**
```bash
# User visits production website
# Makes annotations to HB727 fiscal note
# Annotations saved to: src/fiscal_notes/generation/HB_727_2025/fiscal_notes/HB727.json

# Later, you deploy code update
git push origin main

# Jenkins:
# 1. Stashes HB727.json (with annotations)
# 2. Pulls code
# 3. Restores HB727.json
```

**Result:** ✅ User annotations preserved!

---

### **Scenario 4: Sync Fiscal Notes from Production to Dev**
If you want to get production fiscal notes (with user annotations) to dev:

```bash
# On production server
cd /home/exouser/RAG-system
tar -czf fiscal_notes_backup.tar.gz src/fiscal_notes/generation/

# Copy to dev
scp exouser@production:/home/exouser/RAG-system/fiscal_notes_backup.tar.gz .

# On dev machine
tar -xzf fiscal_notes_backup.tar.gz
```

**Result:** ✅ Production fiscal notes (with annotations) copied to dev!

---

## ⚠️ Important Notes

### **1. Files Already on Production Are Safe**
- All fiscal notes pushed earlier are on production
- They won't be deleted by future deployments
- User annotations will be preserved

### **2. New Fiscal Notes Won't Auto-Deploy**
- If you generate new fiscal notes on dev, they stay local
- To deploy new fiscal notes to production:
  ```bash
  # Option A: Manually copy to production
  scp -r src/fiscal_notes/generation/HB_1234_2025/ exouser@production:/home/exouser/RAG-system/src/fiscal_notes/generation/
  
  # Option B: Temporarily remove from .gitignore, commit, push, then re-add to .gitignore
  ```

### **3. Python Scripts Are Still Tracked**
- Changes to generation scripts (`.py` files) are tracked
- They will deploy to production automatically
- This is intentional - code should sync, data should not

### **4. Git Stash Protects User Data**
- If git pull would delete fiscal notes, stash saves them first
- After pull, stash pop restores them
- This happens automatically during Jenkins deployment

---

## 🔍 Verification

### **Check What's Tracked:**
```bash
git ls-files src/fiscal_notes/generation/
# Should show only .py and .md files
```

### **Check What's Ignored:**
```bash
git status --ignored src/fiscal_notes/generation/
# Should show HB_*/, SB_*/, september_archive/ as ignored
```

### **Check Production Fiscal Notes:**
```bash
ssh exouser@production
cd /home/exouser/RAG-system
ls -la src/fiscal_notes/generation/
# Should show all fiscal note directories
```

---

## 📊 Summary

| Aspect | Dev | Production |
|--------|-----|------------|
| **Fiscal Notes** | Local only | Local only |
| **User Annotations** | N/A | Preserved |
| **Python Scripts** | Tracked | Synced |
| **Code Updates** | Push to Git | Auto-deploy |
| **New Fiscal Notes** | Stay local | Manual copy |

---

## ✅ Benefits

1. **User Annotations Protected** - Never overwritten by deployments
2. **Dev/Prod Separation** - Generate test fiscal notes without affecting production
3. **Code Still Syncs** - Python scripts and frontend code deploy normally
4. **Backup Safety** - Fiscal notes on production are backed up locally
5. **Flexible** - Can manually sync fiscal notes when needed

---

## 🎉 Result

**Dev and production are now properly separated!**
- ✅ Code updates deploy automatically
- ✅ User annotations are preserved
- ✅ New fiscal notes stay local to dev
- ✅ Python scripts stay in sync

**Your production users' annotations are safe!** 🎉
