from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import desc
from typing import List, Optional
from pydantic import BaseModel, field_serializer
from datetime import datetime
import logging
import json

from database.connection import get_db
from database.models import User, Permission, UserPermission, AuditLog
from auth.middleware import require_admin, get_current_user
from auth.permissions import permission_checker

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/admin", tags=["admin"])

# Pydantic models for API responses
class UserSummary(BaseModel):
    id: int
    auth0_user_id: str
    email: str
    display_name: str
    is_active: bool
    is_admin: bool
    created_at: str
    updated_at: str
    permission_count: int
    
    @field_serializer('created_at', 'updated_at')
    def serialize_datetime(self, value):
        if isinstance(value, datetime):
            return value.isoformat()
        return value
    
    class Config:
        from_attributes = True

class CreateUserRequest(BaseModel):
    email: str
    display_name: str
    is_admin: bool = False

class UpdateUserPermissionsRequest(BaseModel):
    permission_names: List[str]

class UserSummaryWithPermissions(BaseModel):
    id: int
    auth0_user_id: str
    email: str
    display_name: str
    is_active: bool
    is_admin: bool
    created_at: str
    updated_at: str
    permissions: List[str]  # List of permission names
    
    @field_serializer('created_at', 'updated_at')
    def serialize_datetime(self, value):
        if isinstance(value, datetime):
            return value.isoformat()
        return value
    
    class Config:
        from_attributes = True

class PermissionSummary(BaseModel):
    id: int
    name: str
    description: str
    category: str
    created_at: str
    user_count: int
    
    class Config:
        from_attributes = True

class UserPermissionDetail(BaseModel):
    permission_id: int
    permission_name: str
    permission_description: str
    granted_at: str
    granted_by_email: str

class UserDetailResponse(BaseModel):
    user: UserSummary
    permissions: List[UserPermissionDetail]

class AuditLogEntry(BaseModel):
    id: int
    user_email: Optional[str]
    action: str
    resource: Optional[str]
    details: Optional[str]
    ip_address: Optional[str]
    timestamp: str

class UpdateUserRequest(BaseModel):
    display_name: Optional[str] = None
    is_active: Optional[bool] = None

@router.get("/users", response_model=List[UserSummaryWithPermissions])
async def list_users(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    active_only: bool = Query(True),
    admin_user: User = Depends(require_admin()),
    db: Session = Depends(get_db)
):
    """List all users with pagination and their permissions"""
    try:
        query = db.query(User)
        
        if active_only:
            query = query.filter(User.is_active == True)
        
        users = query.offset(skip).limit(limit).all()
        
        # Get permissions for each user
        user_summaries = []
        for user in users:
            # Get user permissions
            user_permissions = (
                db.query(Permission.name)
                .join(UserPermission, Permission.id == UserPermission.permission_id)
                .filter(UserPermission.user_id == user.id)
                .all()
            )
            permission_names = [perm.name for perm in user_permissions]
            
            user_summary = UserSummaryWithPermissions(
                id=user.id,
                auth0_user_id=user.auth0_user_id,
                email=user.email,
                display_name=user.display_name,
                is_active=user.is_active,
                is_admin=user.is_admin,
                created_at=user.created_at.isoformat(),
                updated_at=user.updated_at.isoformat(),
                permissions=permission_names
            )
            user_summaries.append(user_summary)
        
        return user_summaries
        
    except Exception as e:
        logger.error(f"Error listing users: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.post("/users", response_model=UserSummary)
async def create_user(
    user_data: CreateUserRequest,
    admin_user: User = Depends(require_admin()),
    db: Session = Depends(get_db)
):
    """Create a new user (admin only)"""
    try:
        # Check if user already exists
        existing_user = db.query(User).filter_by(email=user_data.email).first()
        if existing_user:
            raise HTTPException(status_code=400, detail="User with this email already exists")
        
        # Create new user (without auth0_user_id since they haven't logged in yet)
        new_user = User(
            auth0_user_id="",  # Will be set when they first log in
            email=user_data.email,
            display_name=user_data.display_name,
            is_active=True,
            is_admin=user_data.is_admin
        )
        
        db.add(new_user)
        db.flush()  # Get the user ID
        
        # Log user creation
        audit_log = AuditLog(
            user_id=admin_user.id,
            action="user_created",
            resource="user_management",
            details=json.dumps({
                "created_user_email": user_data.email,
                "created_user_id": new_user.id,
                "is_admin": user_data.is_admin
            })
        )
        db.add(audit_log)
        db.commit()
        
        logger.info(f"Admin {admin_user.email} created user: {user_data.email}")
        
        # Return user summary with permission count
        return UserSummary(
            id=new_user.id,
            auth0_user_id=new_user.auth0_user_id,
            email=new_user.email,
            display_name=new_user.display_name,
            is_active=new_user.is_active,
            is_admin=new_user.is_admin,
            created_at=new_user.created_at.isoformat(),
            updated_at=new_user.updated_at.isoformat(),
            permission_count=0  # New user has no permissions yet
        )
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Error creating user: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.put("/users/{user_id}/permissions")
async def update_user_permissions(
    user_id: int,
    permissions_data: UpdateUserPermissionsRequest,
    admin_user: User = Depends(require_admin()),
    db: Session = Depends(get_db)
):
    """Update user permissions (admin only)"""
    try:
        # Get the user
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        # Clear existing permissions
        db.query(UserPermission).filter(UserPermission.user_id == user_id).delete()
        
        # Add new permissions
        for permission_name in permissions_data.permission_names:
            permission = db.query(Permission).filter(Permission.name == permission_name).first()
            if permission:
                user_permission = UserPermission(
                    user_id=user_id,
                    permission_id=permission.id
                )
                db.add(user_permission)
        
        # Log permission update
        audit_log = AuditLog(
            user_id=admin_user.id,
            action="permissions_updated",
            resource="user_management",
            details=json.dumps({
                "target_user_email": user.email,
                "target_user_id": user_id,
                "permissions": permissions_data.permission_names
            })
        )
        db.add(audit_log)
        db.commit()
        
        logger.info(f"Admin {admin_user.email} updated permissions for user {user.email}: {permissions_data.permission_names}")
        
        return {"message": "Permissions updated successfully", "user_id": user_id}
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Error updating user permissions: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.get("/users/{user_id}", response_model=UserDetailResponse)
async def get_user_detail(
    user_id: int,
    admin_user: User = Depends(require_admin()),
    db: Session = Depends(get_db)
):
    """Get detailed information about a specific user"""
    try:
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        # Get user permissions with granter information
        permissions_query = (
            db.query(Permission, UserPermission, User)
            .join(UserPermission, Permission.id == UserPermission.permission_id)
            .outerjoin(User, User.id == UserPermission.granted_by)
            .filter(UserPermission.user_id == user_id)
            .all()
        )
        
        permissions = [
            UserPermissionDetail(
                permission_id=perm.id,
                permission_name=perm.name,
                permission_description=perm.description or "",
                granted_at=user_perm.granted_at.isoformat(),
                granted_by_email=granter.email if granter else "System"
            )
            for perm, user_perm, granter in permissions_query
        ]
        
        user_summary = UserSummary(
            id=user.id,
            auth0_user_id=user.auth0_user_id,
            email=user.email,
            display_name=user.display_name or "",
            is_active=user.is_active,
            is_admin=user.is_admin,
            created_at=user.created_at.isoformat(),
            updated_at=user.updated_at.isoformat(),
            permission_count=len(permissions)
        )
        
        return UserDetailResponse(user=user_summary, permissions=permissions)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting user detail: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.put("/users/{user_id}", response_model=UserSummary)
async def update_user(
    user_id: int,
    update_request: UpdateUserRequest,
    admin_user: User = Depends(require_admin()),
    db: Session = Depends(get_db)
):
    """Update user information"""
    try:
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        # Update fields if provided
        if update_request.display_name is not None:
            user.display_name = update_request.display_name
        
        if update_request.is_active is not None:
            user.is_active = update_request.is_active
        
        db.commit()
        db.refresh(user)
        
        # Get permission count
        permission_count = (
            db.query(UserPermission)
            .filter(UserPermission.user_id == user.id)
            .count()
        )
        
        logger.info(f"Admin {admin_user.email} updated user {user.email}")
        
        return UserSummary(
            id=user.id,
            auth0_user_id=user.auth0_user_id,
            email=user.email,
            display_name=user.display_name or "",
            is_active=user.is_active,
            is_admin=user.is_admin,
            created_at=user.created_at.isoformat(),
            updated_at=user.updated_at.isoformat(),
            permission_count=permission_count
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating user: {e}")
        db.rollback()
        raise HTTPException(status_code=500, detail="Internal server error")

@router.post("/users/{user_id}/permissions/{permission_id}")
async def grant_permission(
    user_id: int,
    permission_id: int,
    admin_user: User = Depends(require_admin()),
    db: Session = Depends(get_db)
):
    """Grant a permission to a user"""
    try:
        # Verify user exists
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        # Verify permission exists
        permission = db.query(Permission).filter(Permission.id == permission_id).first()
        if not permission:
            raise HTTPException(status_code=404, detail="Permission not found")
        
        # Grant permission
        granted = permission_checker.grant_permission(
            user_id=user_id,
            permission_name=permission.name,
            granted_by_id=admin_user.id,
            session=db
        )
        
        if not granted:
            raise HTTPException(status_code=400, detail="User already has this permission")
        
        db.commit()
        
        logger.info(f"Admin {admin_user.email} granted permission {permission.name} to {user.email}")
        
        return {
            "message": f"Permission '{permission.name}' granted to user {user.email}",
            "user_id": user_id,
            "permission_id": permission_id
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error granting permission: {e}")
        db.rollback()
        raise HTTPException(status_code=500, detail="Internal server error")

@router.delete("/users/{user_id}/permissions/{permission_id}")
async def revoke_permission(
    user_id: int,
    permission_id: int,
    admin_user: User = Depends(require_admin()),
    db: Session = Depends(get_db)
):
    """Revoke a permission from a user"""
    try:
        # Verify user exists
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        # Verify permission exists
        permission = db.query(Permission).filter(Permission.id == permission_id).first()
        if not permission:
            raise HTTPException(status_code=404, detail="Permission not found")
        
        # Revoke permission
        revoked = permission_checker.revoke_permission(
            user_id=user_id,
            permission_name=permission.name,
            revoked_by_id=admin_user.id,
            session=db
        )
        
        if not revoked:
            raise HTTPException(status_code=400, detail="User does not have this permission")
        
        db.commit()
        
        logger.info(f"Admin {admin_user.email} revoked permission {permission.name} from {user.email}")
        
        return {
            "message": f"Permission '{permission.name}' revoked from user {user.email}",
            "user_id": user_id,
            "permission_id": permission_id
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error revoking permission: {e}")
        db.rollback()
        raise HTTPException(status_code=500, detail="Internal server error")

@router.get("/permissions", response_model=List[PermissionSummary])
async def list_permissions(
    admin_user: User = Depends(require_admin()),
    db: Session = Depends(get_db)
):
    """List all available permissions"""
    try:
        permissions = db.query(Permission).all()
        
        permission_summaries = []
        for permission in permissions:
            user_count = (
                db.query(UserPermission)
                .filter(UserPermission.permission_id == permission.id)
                .count()
            )
            
            permission_summary = PermissionSummary(
                id=permission.id,
                name=permission.name,
                description=permission.description or "",
                category=permission.category,
                created_at=permission.created_at.isoformat(),
                user_count=user_count
            )
            permission_summaries.append(permission_summary)
        
        return permission_summaries
        
    except Exception as e:
        logger.error(f"Error listing permissions: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.get("/audit-log", response_model=List[AuditLogEntry])
async def get_audit_log(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    action: Optional[str] = Query(None),
    admin_user: User = Depends(require_admin()),
    db: Session = Depends(get_db)
):
    """Get audit log entries"""
    try:
        query = (
            db.query(AuditLog, User)
            .outerjoin(User, AuditLog.user_id == User.id)
            .order_by(desc(AuditLog.timestamp))
        )
        
        if action:
            query = query.filter(AuditLog.action == action)
        
        results = query.offset(skip).limit(limit).all()
        
        audit_entries = [
            AuditLogEntry(
                id=log.id,
                user_email=user.email if user else None,
                action=log.action,
                resource=log.resource,
                details=log.details,
                ip_address=log.ip_address,
                timestamp=log.timestamp.isoformat()
            )
            for log, user in results
        ]
        
        return audit_entries
        
    except Exception as e:
        logger.error(f"Error getting audit log: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")
