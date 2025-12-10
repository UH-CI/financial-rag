# 🚀 Production Deployment Guide - Super Admin Feature

## ⚠️ CRITICAL: Read This Before Deploying

This deployment adds the `is_super_admin` column to the database and updates the user management system. **Existing production users will be affected.**

---

## 📋 Pre-Deployment Checklist

### 1. **Backup Production Database**
```bash
# Create a full database backup
cp /path/to/production/database/users.db /path/to/backup/users_backup_$(date +%Y%m%d_%H%M%S).db
```

### 2. **Test Migration in Staging**
```bash
# Run migration script in staging environment first
cd /path/to/your/app/src/database
python production_migration_super_admin.py
```

### 3. **Verify Current Production State**
```bash
# Check current admin users
sqlite3 /path/to/production/database/users.db "SELECT email, is_admin FROM users WHERE is_admin = 1;"
```

---

## 🚀 Deployment Steps

### Step 1: Deploy Code (Without Starting App)
```bash
# Pull latest code
git pull origin main

# Build new Docker images (don't start yet)
docker-compose build

# Stop current application
docker-compose down
```

### Step 2: Run Database Migration
```bash
# Navigate to database directory
cd src/database

# Run the production migration script
python production_migration_super_admin.py

# Verify migration was successful
python production_migration_super_admin.py --verify-only
```

**Expected Output:**
```
✅ is_super_admin column added successfully
✅ tabalbar@hawaii.edu set as super admin
📊 Current admin hierarchy:
  - tabalbar@hawaii.edu: Super Admin
  - [other admins]: Admin
🎉 Production migration completed successfully!
```

### Step 3: Start Application
```bash
# Start the application with new code
docker-compose up -d

# Check logs for any errors
docker-compose logs -f api
```

### Step 4: Verify Deployment
```bash
# Test API endpoints
curl -X GET http://your-domain/api/health

# Check admin panel functionality
# - Log in as tabalbar@hawaii.edu
# - Verify "Super Admin" badge appears
# - Test creating new users with super admin option
```

---

## 🧪 Post-Deployment Testing

### 1. **Admin Panel Tests**
- [ ] Log in as `tabalbar@hawaii.edu`
- [ ] Verify "Super Admin" badge shows (purple)
- [ ] Check admin stats show "1 Super Admin"
- [ ] Test creating new admin users
- [ ] Test creating new super admin users
- [ ] Verify delete buttons appear for admin users

### 2. **API Tests**
```bash
# Test user profile endpoint
curl -H "Authorization: Bearer YOUR_TOKEN" http://your-domain/api/users/profile

# Should include: "is_super_admin": true

# Test admin users endpoint  
curl -H "Authorization: Bearer YOUR_TOKEN" http://your-domain/api/admin/users

# Should include "is_super_admin" field for all users
```

### 3. **Database Verification**
```bash
# Check database schema
sqlite3 /path/to/production/database/users.db ".schema users"

# Should include: is_super_admin BOOLEAN DEFAULT 0 NOT NULL

# Check super admin users
sqlite3 /path/to/production/database/users.db "SELECT email, is_admin, is_super_admin FROM users WHERE is_super_admin = 1;"
```

---

## 🆘 Rollback Plan (If Something Goes Wrong)

### Option 1: Quick Rollback (Recommended)
```bash
# Stop new application
docker-compose down

# Restore previous code version
git checkout HEAD~1  # or specific commit hash

# Restore database backup
cp /path/to/backup/users_backup_YYYYMMDD_HHMMSS.db /path/to/production/database/users.db

# Start previous version
docker-compose up -d
```

### Option 2: Database-Only Rollback
```bash
# If you want to keep new code but rollback database changes
cd src/database
python production_migration_super_admin.py --rollback

# Note: SQLite doesn't support DROP COLUMN, so you may need to restore from backup
```

---

## 🔧 Troubleshooting

### Issue: "Column 'is_super_admin' doesn't exist"
**Solution:**
```bash
# Re-run migration
cd src/database
python production_migration_super_admin.py
```

### Issue: "No super admins showing in admin panel"
**Solution:**
```bash
# Check database
sqlite3 /path/to/production/database/users.db "SELECT email, is_super_admin FROM users WHERE email = 'tabalbar@hawaii.edu';"

# If is_super_admin is 0, fix it:
sqlite3 /path/to/production/database/users.db "UPDATE users SET is_super_admin = 1 WHERE email = 'tabalbar@hawaii.edu';"

# Restart application
docker-compose restart api
```

### Issue: "500 errors on user creation"
**Solution:**
```bash
# Check logs
docker-compose logs api

# Usually means Pydantic model mismatch - verify all UserSummary models include is_super_admin
```

---

## 📞 Emergency Contacts

If deployment fails:
1. **Immediate**: Restore from backup (Option 1 above)
2. **Check logs**: `docker-compose logs api`
3. **Database issues**: Use SQLite browser to inspect database
4. **API issues**: Check network tab in browser for error details

---

## ✅ Success Criteria

Deployment is successful when:
- [ ] Application starts without errors
- [ ] `tabalbar@hawaii.edu` shows as "Super Admin" in admin panel
- [ ] Admin stats show correct super admin count
- [ ] Can create new users with super admin option
- [ ] All existing functionality still works
- [ ] No 500 errors in logs

---

## 🧹 Cleanup (After Successful Deployment)

After 24-48 hours of stable operation:
```bash
# Remove backup table from database
sqlite3 /path/to/production/database/users.db "DROP TABLE IF EXISTS users_backup_pre_super_admin;"

# Remove old database backup files (keep at least 1 week)
find /path/to/backup/ -name "users_backup_*.db" -mtime +7 -delete
```
