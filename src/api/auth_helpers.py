"""
Auth0 helper functions for user management and email verification
"""

import os
import requests
import logging
from typing import Dict, Any
from fastapi import HTTPException

logger = logging.getLogger(__name__)

class Auth0ManagementAPI:
    """Helper class for Auth0 Management API operations"""
    
    def __init__(self):
        self.domain = os.getenv('AUTH0_DOMAIN')
        self.m2m_client_id = os.getenv('AUTH0_M2M_CLIENT_ID')
        self.m2m_client_secret = os.getenv('AUTH0_M2M_CLIENT_SECRET')
        self.client_id = os.getenv('AUTH0_CLIENT_ID')  # Your main app client ID
        
        if not all([self.domain, self.m2m_client_id, self.m2m_client_secret, self.client_id]):
            raise ValueError("Missing required Auth0 environment variables")
    
    async def get_management_token(self) -> str:
        """Get an access token for the Auth0 Management API"""
        try:
            token_url = f"https://{self.domain}/oauth/token"
            payload = {
                "client_id": self.m2m_client_id,
                "client_secret": self.m2m_client_secret,
                "audience": f"https://{self.domain}/api/v2/",
                "grant_type": "client_credentials"
            }
            
            response = requests.post(token_url, json=payload, timeout=10)
            response.raise_for_status()
            
            token_data = response.json()
            return token_data['access_token']
            
        except requests.RequestException as e:
            logger.error(f"Failed to get Management API token: {e}")
            raise HTTPException(status_code=500, detail="Failed to authenticate with Auth0")
    
    async def get_user_by_email(self, email: str) -> Dict[str, Any]:
        """Get user information by email address"""
        try:
            token = await self.get_management_token()
            
            # Search for user by email
            search_url = f"https://{self.domain}/api/v2/users"
            headers = {
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json"
            }
            params = {
                "q": f'email:"{email}"',
                "search_engine": "v3"
            }
            
            response = requests.get(search_url, headers=headers, params=params, timeout=10)
            response.raise_for_status()
            
            users = response.json()
            if not users:
                raise HTTPException(status_code=404, detail="User not found")
            
            return users[0]  # Return first matching user
            
        except requests.RequestException as e:
            logger.error(f"Failed to get user by email: {e}")
            raise HTTPException(status_code=500, detail="Failed to retrieve user information")
    
    async def send_verification_email(self, user_email: str) -> Dict[str, str]:
        """Send email verification to a user"""
        try:
            # First, get the user to get their Auth0 user_id
            user = await self.get_user_by_email(user_email)
            user_id = user['user_id']
            
            # Get management token
            token = await self.get_management_token()
            
            # Create email verification ticket
            ticket_url = f"https://{self.domain}/api/v2/tickets/email-verification"
            headers = {
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json"
            }
            payload = {
                "user_id": user_id,
                "client_id": self.client_id,
                "ttl_sec": 432000  # 5 days expiration
            }
            
            response = requests.post(ticket_url, json=payload, headers=headers, timeout=10)
            response.raise_for_status()
            
            ticket_data = response.json()
            logger.info(f"Verification email sent successfully to {user_email}")
            
            return {
                "message": "Verification email sent successfully",
                "ticket_url": ticket_data.get("ticket", "")
            }
            
        except HTTPException:
            raise
        except requests.RequestException as e:
            logger.error(f"Failed to send verification email: {e}")
            if hasattr(e, 'response') and e.response is not None:
                logger.error(f"Response content: {e.response.text}")
            raise HTTPException(status_code=500, detail="Failed to send verification email")
        except Exception as e:
            logger.error(f"Unexpected error sending verification email: {e}")
            raise HTTPException(status_code=500, detail="Internal server error")
    
    async def delete_user_from_auth0(self, user_email: str) -> Dict[str, str]:
        """Delete a user from Auth0 by email address"""
        try:
            # First, get the user to get their Auth0 user_id
            user = await self.get_user_by_email(user_email)
            user_id = user['user_id']
            
            # Get management token
            token = await self.get_management_token()
            
            # Delete user from Auth0
            delete_url = f"https://{self.domain}/api/v2/users/{user_id}"
            headers = {
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json"
            }
            
            response = requests.delete(delete_url, headers=headers, timeout=10)
            response.raise_for_status()
            
            logger.info(f"User deleted successfully from Auth0: {user_email}")
            
            return {
                "message": f"User {user_email} deleted successfully from Auth0",
                "user_id": user_id
            }
            
        except HTTPException:
            raise
        except requests.RequestException as e:
            logger.error(f"Failed to delete user from Auth0: {e}")
            if hasattr(e, 'response') and e.response is not None:
                logger.error(f"Response content: {e.response.text}")
            raise HTTPException(status_code=500, detail="Failed to delete user from Auth0")
        except Exception as e:
            logger.error(f"Unexpected error deleting user from Auth0: {e}")
            raise HTTPException(status_code=500, detail="Internal server error")

# Global instance
auth0_mgmt = Auth0ManagementAPI()
