#!/usr/bin/env python3
"""
Database migration script to add email_verified column to existing users table.
Run this script once to update your existing database schema.
"""

import os
import sys
from sqlalchemy import text
from pathlib import Path

# Add the src directory to the Python path
src_path = Path(__file__).parent.parent
sys.path.insert(0, str(src_path))

from database.connection import db_manager
from database.models import User

def migrate_add_email_verified():
    """Add email_verified column to users table and set default values"""
    
    print("🔄 Starting migration: Add email_verified column...")
    
    try:
        with db_manager.get_session() as session:
            # Check if column already exists
            result = session.execute(text("PRAGMA table_info(users)"))
            columns = [row[1] for row in result.fetchall()]
            
            if 'email_verified' in columns:
                print("✅ Column 'email_verified' already exists. Migration not needed.")
                return
            
            # Add the new column
            print("📝 Adding email_verified column...")
            session.execute(text("ALTER TABLE users ADD COLUMN email_verified BOOLEAN DEFAULT 0 NOT NULL"))
            
            # Update existing users - set email_verified to True for admin users, False for others
            print("🔄 Setting default values for existing users...")
            
            # Set admin users as verified (assuming they're trusted)
            admin_count = session.execute(text(
                "UPDATE users SET email_verified = 1 WHERE is_admin = 1"
            )).rowcount
            
            # Set non-admin users as unverified (they'll need to verify)
            user_count = session.execute(text(
                "UPDATE users SET email_verified = 0 WHERE is_admin = 0"
            )).rowcount
            
            session.commit()
            
            print(f"✅ Migration completed successfully!")
            print(f"   - Admin users set as verified: {admin_count}")
            print(f"   - Regular users set as unverified: {user_count}")
            print(f"   - Regular users will need to verify their email on next login")
            
    except Exception as e:
        print(f"❌ Migration failed: {e}")
        raise

def rollback_email_verified():
    """Remove email_verified column (rollback migration)"""
    
    print("🔄 Rolling back migration: Remove email_verified column...")
    
    try:
        with db_manager.get_session() as session:
            # SQLite doesn't support DROP COLUMN directly, so we need to recreate the table
            print("⚠️  SQLite doesn't support DROP COLUMN. Manual rollback required.")
            print("   To rollback, you would need to:")
            print("   1. Export your data")
            print("   2. Drop the users table")
            print("   3. Recreate it without email_verified column")
            print("   4. Re-import your data")
            
    except Exception as e:
        print(f"❌ Rollback failed: {e}")
        raise

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Database migration for email verification")
    parser.add_argument("--rollback", action="store_true", help="Rollback the migration")
    
    args = parser.parse_args()
    
    if args.rollback:
        rollback_email_verified()
    else:
        migrate_add_email_verified()
