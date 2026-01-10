#!/usr/bin/env python3
"""
Production Migration Script for Super Admin Feature
==================================================

This script safely adds the is_super_admin column to production database
and sets up proper super admin permissions.

IMPORTANT: Run this AFTER deploying the new code but BEFORE the application starts..
"""

import os
import sys
from pathlib import Path
from sqlalchemy import text, inspect
import logging

# Add the src directory to the Python path
src_path = Path(__file__).parent.parent
sys.path.insert(0, str(src_path))

from database.connection import db_manager

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def check_column_exists(session, table_name, column_name):
    """Check if a column exists in the table"""
    try:
        inspector = inspect(session.bind)
        columns = [col['name'] for col in inspector.get_columns(table_name)]
        return column_name in columns
    except Exception as e:
        logger.error(f"Error checking column existence: {e}")
        return False

def backup_users_table(session):
    """Create a backup of the users table before migration"""
    try:
        logger.info("Creating backup of users table...")
        session.execute(text("""
            CREATE TABLE IF NOT EXISTS users_backup_pre_super_admin AS 
            SELECT * FROM users
        """))
        session.commit()
        logger.info("✅ Users table backed up successfully")
        return True
    except Exception as e:
        logger.error(f"❌ Failed to backup users table: {e}")
        return False

def add_super_admin_column(session):
    """Add the is_super_admin column if it doesn't exist"""
    try:
        if check_column_exists(session, 'users', 'is_super_admin'):
            logger.info("✅ is_super_admin column already exists")
            return True
        
        logger.info("Adding is_super_admin column...")
        session.execute(text("""
            ALTER TABLE users 
            ADD COLUMN is_super_admin BOOLEAN DEFAULT 0 NOT NULL
        """))
        session.commit()
        logger.info("✅ is_super_admin column added successfully")
        return True
    except Exception as e:
        logger.error(f"❌ Failed to add is_super_admin column: {e}")
        return False

def set_super_admin_users(session, super_admin_emails=None):
    """Set specific users as super admins"""
    if super_admin_emails is None:
        super_admin_emails = ['tabalbar@hawaii.edu']
    
    try:
        for email in super_admin_emails:
            logger.info(f"Setting {email} as super admin...")
            result = session.execute(text("""
                UPDATE users 
                SET is_super_admin = 1, is_admin = 1 
                WHERE email = :email
            """), {"email": email})
            
            if result.rowcount > 0:
                logger.info(f"✅ {email} set as super admin")
            else:
                logger.warning(f"⚠️ User {email} not found in database")
        
        session.commit()
        return True
    except Exception as e:
        logger.error(f"❌ Failed to set super admin users: {e}")
        return False

def verify_migration(session):
    """Verify the migration was successful"""
    try:
        logger.info("Verifying migration...")
        
        # Check column exists
        if not check_column_exists(session, 'users', 'is_super_admin'):
            logger.error("❌ is_super_admin column not found after migration")
            return False
        
        # Check super admin count
        result = session.execute(text("""
            SELECT COUNT(*) as count FROM users WHERE is_super_admin = 1
        """))
        super_admin_count = result.fetchone()[0]
        
        # Check admin hierarchy
        result = session.execute(text("""
            SELECT email, is_admin, is_super_admin 
            FROM users 
            WHERE is_admin = 1 OR is_super_admin = 1
            ORDER BY is_super_admin DESC, is_admin DESC
        """))
        
        logger.info("📊 Current admin hierarchy:")
        for row in result.fetchall():
            role = 'Super Admin' if row[2] else ('Admin' if row[1] else 'User')
            logger.info(f"  - {row[0]}: {role}")
        
        logger.info(f"✅ Migration verified: {super_admin_count} super admin(s) found")
        return True
        
    except Exception as e:
        logger.error(f"❌ Migration verification failed: {e}")
        return False

def rollback_migration(session):
    """Rollback the migration if needed"""
    try:
        logger.info("Rolling back migration...")
        
        # Remove the column (SQLite doesn't support DROP COLUMN directly)
        logger.warning("⚠️ SQLite doesn't support DROP COLUMN. Manual rollback required.")
        logger.info("To rollback manually:")
        logger.info("1. Restore from users_backup_pre_super_admin table")
        logger.info("2. Or recreate the users table without is_super_admin column")
        
        return True
    except Exception as e:
        logger.error(f"❌ Rollback failed: {e}")
        return False

def main():
    """Main migration function"""
    logger.info("🚀 Starting production super admin migration...")
    
    try:
        with db_manager.get_session() as session:
            # Step 1: Backup existing data
            if not backup_users_table(session):
                logger.error("❌ Migration aborted: Backup failed")
                return False
            
            # Step 2: Add the column
            if not add_super_admin_column(session):
                logger.error("❌ Migration aborted: Column addition failed")
                return False
            
            # Step 3: Set super admin users
            # You can customize this list for your production environment
            super_admin_emails = [
                'tabalbar@hawaii.edu',
                'v.chang@capitol.hawaii.gov'
            ]
            
            if not set_super_admin_users(session, super_admin_emails):
                logger.error("❌ Migration aborted: Super admin setup failed")
                return False
            
            # Step 4: Verify migration
            if not verify_migration(session):
                logger.error("❌ Migration verification failed")
                return False
            
            logger.info("🎉 Production migration completed successfully!")
            logger.info("")
            logger.info("📋 Next steps:")
            logger.info("1. Restart your application")
            logger.info("2. Test the admin panel")
            logger.info("3. Verify super admin functionality")
            logger.info("4. Remove backup table when confident: DROP TABLE users_backup_pre_super_admin")
            
            return True
            
    except Exception as e:
        logger.error(f"❌ Migration failed: {e}")
        return False

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Production super admin migration")
    parser.add_argument("--rollback", action="store_true", help="Rollback the migration")
    parser.add_argument("--verify-only", action="store_true", help="Only verify migration status")
    
    args = parser.parse_args()
    
    if args.rollback:
        with db_manager.get_session() as session:
            rollback_migration(session)
    elif args.verify_only:
        with db_manager.get_session() as session:
            verify_migration(session)
    else:
        success = main()
        sys.exit(0 if success else 1)
