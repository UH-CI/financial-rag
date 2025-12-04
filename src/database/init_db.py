#!/usr/bin/env python3
"""
Database initialization script for the Financial RAG user permissions system.
This script creates the database tables and populates them with default data.
"""

import os
import sys
from datetime import datetime

# Add the src directory to the Python path
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from database.connection import db_manager
from database.models import User, Permission, UserPermission, AuditLog

def init_permissions():
    """Initialize default permissions in the database"""
    default_permissions = [
        {
            'name': 'fiscal-note-generation',
            'description': 'Access to fiscal note generation tool',
            'category': 'tool'
        },
        {
            'name': 'similar-bill-search',
            'description': 'Access to similar bill search functionality',
            'category': 'tool'
        },
        {
            'name': 'hrs-search',
            'description': 'Access to HRS search functionality',
            'category': 'tool'
        },
        {
            'name': 'admin-panel',
            'description': 'Access to admin panel',
            'category': 'admin'
        },
        {
            'name': 'user-management',
            'description': 'Ability to manage other users and permissions',
            'category': 'admin'
        },
        {
            'name': 'audit-log-view',
            'description': 'Ability to view audit logs',
            'category': 'admin'
        }
    ]
    
    with db_manager.get_session() as session:
        for perm_data in default_permissions:
            # Check if permission already exists
            existing_perm = session.query(Permission).filter_by(name=perm_data['name']).first()
            if not existing_perm:
                permission = Permission(**perm_data)
                session.add(permission)
                print(f"Created permission: {perm_data['name']}")
            else:
                print(f"Permission already exists: {perm_data['name']}")

def init_admin_user():
    """Initialize the default admin user"""
    admin_email = "tabalbar@hawaii.edu"
    
    with db_manager.get_session() as session:
        # Check if admin user already exists
        existing_admin = session.query(User).filter_by(email=admin_email).first()
        if not existing_admin:
            # Create admin user (will be synced with Auth0 on first login)
            admin_user = User(
                auth0_user_id="placeholder_auth0_id",  # Will be updated on first Auth0 sync
                email=admin_email,
                display_name="Admin User",
                is_active=True,
                is_admin=True
            )
            session.add(admin_user)
            session.flush()  # Get the user ID
            
            # Grant all permissions to admin
            permissions = session.query(Permission).all()
            for permission in permissions:
                user_permission = UserPermission(
                    user_id=admin_user.id,
                    permission_id=permission.id,
                    granted_by=admin_user.id  # Self-granted
                )
                session.add(user_permission)
            
            # Log the admin creation
            audit_log = AuditLog(
                user_id=admin_user.id,
                action="admin_user_created",
                resource="user_management",
                details=f"Admin user created for {admin_email}",
                ip_address="127.0.0.1"
            )
            session.add(audit_log)
            
            print(f"Created admin user: {admin_email}")
        else:
            print(f"Admin user already exists: {admin_email}")

def main():
    """Main initialization function"""
    print("Initializing Financial RAG User Permissions Database...")
    
    try:
        # Create all tables
        print("Creating database tables...")
        db_manager.create_tables()
        print("Database tables created successfully!")
        
        # Initialize default permissions
        print("Initializing default permissions...")
        init_permissions()
        
        # Initialize admin user
        print("Initializing admin user...")
        init_admin_user()
        
        print("Database initialization completed successfully!")
        
    except Exception as e:
        print(f"Error during database initialization: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
