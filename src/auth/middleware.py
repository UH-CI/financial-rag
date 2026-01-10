from fastapi import Request, HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from typing import Optional, Dict, Any
import logging

from .token_validator import get_token_validator
from .permissions import permission_checker
from database.connection import get_db
from database.models import User

logger = logging.getLogger(__name__)

# Security scheme for FastAPI
security = HTTPBearer()

class AuthMiddleware:
    """Authentication and authorization middleware"""
    
    @staticmethod
    def get_current_user(
        request: Request,
        credentials: HTTPAuthorizationCredentials = Depends(security),
        db: Session = Depends(get_db)
    ) -> User:
        """
        FastAPI dependency to get current authenticated user
        
        Args:
            request: FastAPI request object
            credentials: HTTP Bearer credentials
            db: Database session
            
        Returns:
            User object
            
        Raises:
            HTTPException: If authentication fails
        """
        try:
            # Enhanced request logging
            logger.info(f"🌐 Auth request: {request.method} {request.url.path}")
            logger.info(f"📋 Request headers: {dict(request.headers)}")
            
            # Log token info for debugging
            if credentials and credentials.credentials:
                token_length = len(credentials.credentials)
                token_preview = credentials.credentials[:20] + "..." + credentials.credentials[-10:] if token_length > 30 else credentials.credentials
                logger.info(f"🔍 Received token (length: {token_length}): {token_preview}")
            else:
                logger.warning("❌ No credentials provided")
                raise HTTPException(status_code=401, detail="No authorization token provided")
            
            # Validate token
            validator = get_token_validator()
            user_info = validator.validate_token(credentials.credentials)
            
            if not user_info:
                raise HTTPException(
                    status_code=401,
                    detail="Invalid or expired token"
                )
            
            # Sync user with database
            user = permission_checker.sync_user_from_auth0(user_info, db)
            
            if not user.is_active:
                raise HTTPException(
                    status_code=403,
                    detail="User account is deactivated"
                )
            
            # Enforce email verification
            if not user.email_verified:
                raise HTTPException(
                    status_code=403,
                    detail="Email verification required. Please check your email and verify your account."
                )
            
            return user
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Authentication error: {e}")
            raise HTTPException(
                status_code=401,
                detail="Authentication failed"
            )
    
    @staticmethod
    def get_current_user_optional(
        request: Request,
        db: Session = Depends(get_db)
    ) -> Optional[User]:
        """
        Optional authentication - returns None if no valid token
        
        Args:
            request: FastAPI request object
            db: Database session
            
        Returns:
            User object or None
        """
        try:
            auth_header = request.headers.get("Authorization")
            if not auth_header:
                return None
            
            validator = get_token_validator()
            token = validator.extract_token_from_header(auth_header)
            if not token:
                return None
            
            user_info = validator.validate_token(token)
            if not user_info:
                return None
            
            user = permission_checker.sync_user_from_auth0(user_info, db)
            return user if user.is_active else None
            
        except Exception as e:
            logger.warning(f"Optional authentication failed: {e}")
            return None

def require_permission(permission_name: str):
    """
    Decorator factory for requiring specific permissions
    
    Args:
        permission_name: Name of the required permission
        
    Returns:
        FastAPI dependency function
    """
    def permission_dependency(
        current_user: User = Depends(AuthMiddleware.get_current_user),
        db: Session = Depends(get_db)
    ) -> User:
        """Check if current user has required permission"""
        
        # Super admin users have all permissions
        if current_user.is_super_admin:
            return current_user
        
        # Regular admin users have all permissions
        if current_user.is_admin:
            return current_user
        
        # Check specific permission
        if not permission_checker.has_permission(current_user.id, permission_name, db):
            # Log access denial
            permission_checker.log_access_attempt(
                user_id=current_user.id,
                resource=permission_name,
                success=False,
                session=db
            )
            
            raise HTTPException(
                status_code=403,
                detail=f"Insufficient permissions. Required: {permission_name}"
            )
        
        # Log successful access
        permission_checker.log_access_attempt(
            user_id=current_user.id,
            resource=permission_name,
            success=True,
            session=db
        )
        
        return current_user
    
    return permission_dependency

def require_admin():
    """
    Decorator for requiring admin privileges
    
    Returns:
        FastAPI dependency function
    """
    def admin_dependency(
        current_user: User = Depends(AuthMiddleware.get_current_user)
    ) -> User:
        """Check if current user is admin"""
        
        if not (current_user.is_admin or current_user.is_super_admin):
            raise HTTPException(
                status_code=403,
                detail="Admin privileges required"
            )
        
        return current_user
    
    return admin_dependency

def require_super_admin():
    """
    Decorator for requiring super admin privileges
    
    Returns:
        FastAPI dependency function
    """
    def super_admin_dependency(
        current_user: User = Depends(AuthMiddleware.get_current_user)
    ) -> User:
        """Check if current user is super admin"""
        
        if not current_user.is_super_admin:
            raise HTTPException(
                status_code=403,
                detail="Super administrator privileges required"
            )
        
        return current_user
    
    return super_admin_dependency

# Convenience dependencies
get_current_user = AuthMiddleware.get_current_user
get_current_user_optional = AuthMiddleware.get_current_user_optional
