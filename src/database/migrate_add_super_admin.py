#!/usr/bin/env python3
"""
Database migration script to add is_super_admin column and set tabalbar@hawaii.edu as super admin.
"""

import os
import sys
from sqlalchemy import text
from pathlib import Path

# Add the src directory to the Python path
src_path = Path(__file__).parent.parent
sys.path.insert(0, str(src_path))

from database.connection import db_manager

def migrate_add_super_admin():
    """Add is_super_admin column and set super admin"""
    
    print("🔄 Starting migration: Add is_super_admin column...")
    
    try:
        with db_manager.get_session() as session:
            # Check if column already exists
            result = session.execute(text("PRAGMA table_info(users)"))
            columns = [row[1] for row in result.fetchall()]
            
            if 'is_super_admin' in columns:
                print("✅ Column 'is_super_admin' already exists. Migration not needed.")
                return
            
            # Add the new column
            print("📝 Adding is_super_admin column...")
            session.execute(text("ALTER TABLE users ADD COLUMN is_super_admin BOOLEAN DEFAULT 0 NOT NULL"))
            
            # Set tabalbar@hawaii.edu as super admin
            print("👑 Setting tabalbar@hawaii.edu as super admin...")
            result = session.execute(text(
                "UPDATE users SET is_super_admin = 1 WHERE email = 'tabalbar@hawaii.edu'"
            ))
            
            if result.rowcount > 0:
                print(f"✅ Successfully set tabalbar@hawaii.edu as super admin")
            else:
                print("⚠️ User tabalbar@hawaii.edu not found - will be set as super admin when they first log in")
            
            # Show current admin status
            print("\n📊 Current admin hierarchy:")
            result = session.execute(text("""
                SELECT email, 
                       CASE WHEN is_super_admin = 1 THEN 'Super Admin'
                            WHEN is_admin = 1 THEN 'Admin' 
                            ELSE 'User' END as role
                FROM users 
                WHERE is_admin = 1 OR is_super_admin = 1
                ORDER BY is_super_admin DESC, is_admin DESC
            """))
            
            for row in result.fetchall():
                print(f"  - {row[0]}: {row[1]}")
            
            session.commit()
            print(f"\n✅ Migration completed successfully!")
            
    except Exception as e:
        print(f"❌ Migration failed: {e}")
        raise

def rollback_super_admin():
    """Remove is_super_admin column (rollback migration)"""
    
    print("🔄 Rolling back migration: Remove is_super_admin column...")
    
    try:
        with db_manager.get_session() as session:
            # SQLite doesn't support DROP COLUMN directly
            print("⚠️  SQLite doesn't support DROP COLUMN. Manual rollback required.")
            print("   To rollback, you would need to recreate the table without is_super_admin column.")
            
    except Exception as e:
        print(f"❌ Rollback failed: {e}")
        raise

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Database migration for super admin")
    parser.add_argument("--rollback", action="store_true", help="Rollback the migration")
    
    args = parser.parse_args()
    
    if args.rollback:
        rollback_super_admin()
    else:
        migrate_add_super_admin()
