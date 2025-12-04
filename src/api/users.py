from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List, Dict, Any
from pydantic import BaseModel, field_serializer
from datetime import datetime
import logging

from database.connection import get_db
from database.models import User, Permission, UserPermission
from auth.middleware import get_current_user
from auth.permissions import permission_checker

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/users", tags=["users"])

# Pydantic models for API responses
class UserProfile(BaseModel):
    id: int
    auth0_user_id: str
    email: str
    display_name: str
    is_active: bool
    is_admin: bool
    created_at: str
    updated_at: str
    
    @field_serializer('created_at', 'updated_at')
    def serialize_datetime(self, value):
        if isinstance(value, datetime):
            return value.isoformat()
        return value
    
    class Config:
        from_attributes = True

class UserPermissionInfo(BaseModel):
    name: str
    description: str
    category: str
    granted_at: str
    
    @field_serializer('granted_at')
    def serialize_datetime(self, value):
        if isinstance(value, datetime):
            return value.isoformat()
        return value

class UserProfileWithPermissions(BaseModel):
    user: UserProfile
    permissions: List[UserPermissionInfo]

class UpdateProfileRequest(BaseModel):
    display_name: str

@router.get("/profile", response_model=UserProfileWithPermissions)
async def get_user_profile(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get current user's profile and permissions"""
    try:
        # Get user permissions with details
        permissions_query = (
            db.query(Permission, UserPermission)
            .join(UserPermission)
            .filter(UserPermission.user_id == current_user.id)
            .all()
        )
        
        permissions = [
            UserPermissionInfo(
                name=perm.name,
                description=perm.description or "",
                category=perm.category,
                granted_at=user_perm.granted_at.isoformat()
            )
            for perm, user_perm in permissions_query
        ]
        
        # Create user profile with proper datetime serialization
        user_profile = UserProfile(
            id=current_user.id,
            auth0_user_id=current_user.auth0_user_id,
            email=current_user.email,
            display_name=current_user.display_name,
            is_active=current_user.is_active,
            is_admin=current_user.is_admin,
            created_at=current_user.created_at.isoformat(),
            updated_at=current_user.updated_at.isoformat()
        )
        
        return UserProfileWithPermissions(
            user=user_profile,
            permissions=permissions
        )
        
    except Exception as e:
        logger.error(f"Error getting user profile: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.put("/profile", response_model=UserProfile)
async def update_user_profile(
    profile_update: UpdateProfileRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Update current user's profile"""
    try:
        current_user.display_name = profile_update.display_name
        db.commit()
        db.refresh(current_user)
        
        logger.info(f"User {current_user.email} updated profile")
        return UserProfile.from_orm(current_user)
        
    except Exception as e:
        logger.error(f"Error updating user profile: {e}")
        db.rollback()
        raise HTTPException(status_code=500, detail="Internal server error")

@router.get("/permissions", response_model=List[str])
async def get_user_permissions(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get current user's permission names"""
    try:
        permissions = permission_checker.get_user_permissions(current_user.id, db)
        return permissions
        
    except Exception as e:
        logger.error(f"Error getting user permissions: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.post("/sync")
async def sync_user_from_auth0(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Force sync current user from Auth0 (user data is already synced by middleware)"""
    try:
        # User is already synced by the middleware, just return success
        logger.info(f"User {current_user.email} requested sync")
        return {
            "message": "User synchronized successfully",
            "user_id": current_user.id,
            "email": current_user.email
        }
        
    except Exception as e:
        logger.error(f"Error syncing user: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")
