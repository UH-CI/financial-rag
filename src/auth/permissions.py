from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session
from database.models import User, Permission, UserPermission, AuditLog
from database.connection import db_manager
import logging
import json

logger = logging.getLogger(__name__)

class PermissionChecker:
    """Handle permission checking and user synchronization"""
    
    @staticmethod
    def sync_user_from_auth0(auth0_user_info: Dict[str, Any], session: Session) -> User:
        """
        Sync user information from Auth0 to local database
        
        Args:
            auth0_user_info: User info from Auth0 token
            session: Database session
            
        Returns:
            User object (created or updated)
        """
        auth0_user_id = auth0_user_info.get("auth0_user_id")
        email = auth0_user_info.get("email")
        
        if not auth0_user_id or not email:
            raise ValueError("Missing required user information from Auth0")
        
        # Check if user exists by auth0_user_id first
        user = session.query(User).filter_by(auth0_user_id=auth0_user_id).first()
        
        if not user:
            # If not found by auth0_user_id, check by email (for existing users)
            user = session.query(User).filter_by(email=email).first()
            if user:
                # Update existing user with new auth0_user_id
                user.auth0_user_id = auth0_user_id
                logger.info(f"Updated existing user with new auth0_user_id: {email}")
        
        if user:
            # Update existing user
            user.email = email
            user.display_name = auth0_user_info.get("display_name") or user.display_name
            user.updated_at = user.updated_at  # This will trigger the onupdate
            logger.info(f"Updated existing user: {email}")
        else:
            # Create new user
            user = User(
                auth0_user_id=auth0_user_id,
                email=email,
                display_name=auth0_user_info.get("display_name"),
                is_active=True,
                is_admin=(email == "tabalbar@hawaii.edu")  # Auto-admin for specific email
            )
            session.add(user)
            logger.info(f"Created new user: {email}")
            session.flush()  # Get the user ID
            
            # Log user creation
            audit_log = AuditLog(
                user_id=user.id,
                action="user_created",
                resource="user_management",
                details=json.dumps({
                    "email": email,
                    "auth0_user_id": auth0_user_id,
                    "source": "auth0_sync"
                })
            )
            session.add(audit_log)
            
            logger.info(f"Created new user: {email}")
        
        return user
    
    @staticmethod
    def get_user_permissions(user_id: int, session: Session) -> List[str]:
        """
        Get list of permission names for a user
        
        Args:
            user_id: User ID
            session: Database session
            
        Returns:
            List of permission names
        """
        permissions = (
            session.query(Permission.name)
            .join(UserPermission)
            .filter(UserPermission.user_id == user_id)
            .all()
        )
        
        return [perm.name for perm in permissions]
    
    @staticmethod
    def has_permission(user_id: int, permission_name: str, session: Session) -> bool:
        """
        Check if user has a specific permission
        
        Args:
            user_id: User ID
            permission_name: Name of the permission to check
            session: Database session
            
        Returns:
            True if user has permission, False otherwise
        """
        permission_exists = (
            session.query(UserPermission)
            .join(Permission)
            .filter(
                UserPermission.user_id == user_id,
                Permission.name == permission_name
            )
            .first()
        )
        
        return permission_exists is not None
    
    @staticmethod
    def grant_permission(user_id: int, permission_name: str, granted_by_id: int, session: Session) -> bool:
        """
        Grant a permission to a user
        
        Args:
            user_id: User ID to grant permission to
            permission_name: Name of the permission
            granted_by_id: ID of user granting the permission
            session: Database session
            
        Returns:
            True if permission was granted, False if already exists
        """
        # Check if permission exists
        permission = session.query(Permission).filter_by(name=permission_name).first()
        if not permission:
            raise ValueError(f"Permission '{permission_name}' does not exist")
        
        # Check if user already has permission
        existing = (
            session.query(UserPermission)
            .filter_by(user_id=user_id, permission_id=permission.id)
            .first()
        )
        
        if existing:
            return False  # Permission already exists
        
        # Grant permission
        user_permission = UserPermission(
            user_id=user_id,
            permission_id=permission.id,
            granted_by=granted_by_id
        )
        session.add(user_permission)
        
        # Log the action
        audit_log = AuditLog(
            user_id=granted_by_id,
            action="permission_granted",
            resource="user_management",
            details=json.dumps({
                "target_user_id": user_id,
                "permission_name": permission_name,
                "permission_id": permission.id
            })
        )
        session.add(audit_log)
        
        logger.info(f"Granted permission '{permission_name}' to user {user_id} by user {granted_by_id}")
        return True
    
    @staticmethod
    def revoke_permission(user_id: int, permission_name: str, revoked_by_id: int, session: Session) -> bool:
        """
        Revoke a permission from a user
        
        Args:
            user_id: User ID to revoke permission from
            permission_name: Name of the permission
            revoked_by_id: ID of user revoking the permission
            session: Database session
            
        Returns:
            True if permission was revoked, False if didn't exist
        """
        # Find the permission
        permission = session.query(Permission).filter_by(name=permission_name).first()
        if not permission:
            raise ValueError(f"Permission '{permission_name}' does not exist")
        
        # Find and delete the user permission
        user_permission = (
            session.query(UserPermission)
            .filter_by(user_id=user_id, permission_id=permission.id)
            .first()
        )
        
        if not user_permission:
            return False  # Permission didn't exist
        
        session.delete(user_permission)
        
        # Log the action
        audit_log = AuditLog(
            user_id=revoked_by_id,
            action="permission_revoked",
            resource="user_management",
            details=json.dumps({
                "target_user_id": user_id,
                "permission_name": permission_name,
                "permission_id": permission.id
            })
        )
        session.add(audit_log)
        
        logger.info(f"Revoked permission '{permission_name}' from user {user_id} by user {revoked_by_id}")
        return True
    
    @staticmethod
    def log_access_attempt(user_id: Optional[int], resource: str, success: bool, 
                          ip_address: str = None, details: Dict = None, session: Session = None):
        """
        Log an access attempt for audit purposes
        
        Args:
            user_id: User ID (None for anonymous attempts)
            resource: Resource being accessed
            success: Whether access was granted
            ip_address: Client IP address
            details: Additional details to log
            session: Database session (optional, will create new if not provided)
        """
        action = "access_granted" if success else "access_denied"
        
        audit_log = AuditLog(
            user_id=user_id,
            action=action,
            resource=resource,
            details=json.dumps(details) if details else None,
            ip_address=ip_address
        )
        
        if session:
            session.add(audit_log)
        else:
            with db_manager.get_session() as new_session:
                new_session.add(audit_log)
        
        logger.info(f"Logged {action} for resource '{resource}' by user {user_id}")

# Convenience instance
permission_checker = PermissionChecker()
