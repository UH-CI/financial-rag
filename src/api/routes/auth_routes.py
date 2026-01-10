"""
Authentication-related API routes
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Dict, Any
import logging

from ..auth_helpers import auth0_mgmt
from database.connection import get_db
from auth.middleware import AuthMiddleware

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["authentication"])

class ResendVerificationRequest(BaseModel):
    email: str

class ResendVerificationResponse(BaseModel):
    message: str
    success: bool

@router.post("/resend-verification", response_model=ResendVerificationResponse)
async def resend_verification_email(
    request: ResendVerificationRequest,
    db: Session = Depends(get_db)
):
    """
    Resend email verification to a user
    
    This endpoint can be called without authentication since users who need
    email verification might not be able to authenticate yet.
    """
    try:
        logger.info(f"Resending verification email to: {request.email}")
        
        # Send verification email via Auth0 Management API
        result = await auth0_mgmt.send_verification_email(request.email)
        
        return ResendVerificationResponse(
            message=result["message"],
            success=True
        )
        
    except HTTPException as e:
        logger.error(f"HTTP error resending verification: {e.detail}")
        raise e
    except Exception as e:
        logger.error(f"Unexpected error resending verification: {e}")
        raise HTTPException(
            status_code=500, 
            detail="Failed to resend verification email"
        )

@router.post("/check-verification-status")
async def check_verification_status(
    request: ResendVerificationRequest,
    db: Session = Depends(get_db)
):
    """
    Check if a user's email is verified in Auth0
    """
    try:
        logger.info(f"Checking verification status for: {request.email}")
        
        # Get user from Auth0
        user = await auth0_mgmt.get_user_by_email(request.email)
        
        return {
            "email": request.email,
            "email_verified": user.get("email_verified", False),
            "user_id": user.get("user_id", ""),
            "last_login": user.get("last_login", None)
        }
        
    except HTTPException as e:
        logger.error(f"HTTP error checking verification status: {e.detail}")
        raise e
    except Exception as e:
        logger.error(f"Unexpected error checking verification status: {e}")
        raise HTTPException(
            status_code=500, 
            detail="Failed to check verification status"
        )
