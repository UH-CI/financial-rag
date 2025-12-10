import jwt
import requests
from typing import Dict, Optional
from functools import lru_cache
import logging
import os
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

class Auth0TokenValidator:
    def __init__(self, domain: str, audience: str):
        self.domain = domain
        self.audience = audience
        self.jwks_url = f"https://{domain}/.well-known/jwks.json"
        self._jwks_cache = None
        self._jwks_cache_time = None
        self._cache_duration = timedelta(hours=1)  # Cache JWKS for 1 hour
    
    @lru_cache(maxsize=10)
    def _get_jwks(self) -> Dict:
        """Get JSON Web Key Set from Auth0 with caching"""
        try:
            if (self._jwks_cache is None or 
                self._jwks_cache_time is None or 
                datetime.utcnow() - self._jwks_cache_time > self._cache_duration):
                
                response = requests.get(self.jwks_url, timeout=10)
                response.raise_for_status()
                self._jwks_cache = response.json()
                self._jwks_cache_time = datetime.utcnow()
                logger.info("JWKS cache refreshed")
            
            return self._jwks_cache
        except Exception as e:
            logger.error(f"Error fetching JWKS: {e}")
            raise ValueError("Unable to fetch Auth0 JWKS")
    
    def _get_signing_key(self, token_header: Dict) -> str:
        """Get the signing key for the JWT token"""
        jwks = self._get_jwks()
        
        for key in jwks.get("keys", []):
            if key.get("kid") == token_header.get("kid"):
                # Construct the key
                if key.get("kty") == "RSA":
                    return jwt.algorithms.RSAAlgorithm.from_jwk(key)
        
        raise ValueError("Unable to find appropriate signing key")
    
    def validate_token(self, token: str) -> Optional[Dict]:
        """
        Validate Auth0 JWT token and return user information
        
        Args:
            token: JWT token string
            
        Returns:
            Dict with user information if valid, None if invalid
        """
        try:
            # Decode token header to get key ID
            unverified_header = jwt.get_unverified_header(token)
            
            # Get signing key
            signing_key = self._get_signing_key(unverified_header)
            
            # Decode and verify token
            payload = jwt.decode(
                token,
                signing_key,
                algorithms=["RS256"],
                audience=self.audience,
                issuer=f"https://{self.domain}/"
            )
            
            # Extract user information
            user_info = {
                "auth0_user_id": payload.get("sub"),
                "email": payload.get("email"),
                "email_verified": payload.get("email_verified", False),
                "display_name": payload.get("name") or payload.get("nickname"),
                "picture": payload.get("picture"),
                "permissions": payload.get("permissions", []),
                "roles": payload.get("https://financial-rag.com/roles", []),  # Custom claim
                "exp": payload.get("exp"),
                "iat": payload.get("iat")
            }
            
            # If email is missing from access token, try to get it from Auth0 userinfo endpoint
            if not user_info.get("email") and user_info.get("auth0_user_id"):
                try:
                    logger.info("Email missing from token, fetching from Auth0 userinfo endpoint")
                    userinfo_url = f"https://{self.domain}/userinfo"
                    headers = {"Authorization": f"Bearer {token}"}
                    response = requests.get(userinfo_url, headers=headers, timeout=10)
                    
                    if response.status_code == 200:
                        userinfo = response.json()
                        user_info["email"] = userinfo.get("email")
                        user_info["email_verified"] = userinfo.get("email_verified", False)
                        user_info["display_name"] = userinfo.get("name") or userinfo.get("nickname") or user_info["display_name"]
                        user_info["picture"] = userinfo.get("picture") or user_info["picture"]
                        logger.info(f"Successfully fetched email from userinfo: {user_info.get('email')}")
                    elif response.status_code == 429:
                        logger.warning("Auth0 userinfo endpoint rate limited (429). Continuing with token data.")
                    else:
                        logger.warning(f"Failed to fetch userinfo: {response.status_code}")
                except Exception as e:
                    logger.warning(f"Error fetching userinfo: {e}")
            
            logger.info(f"Token validated for user: {user_info.get('email')}")
            return user_info
            
        except jwt.ExpiredSignatureError:
            logger.warning("Token has expired")
            return None
        except jwt.InvalidTokenError as e:
            logger.warning(f"Invalid token: {e}")
            return None
        except Exception as e:
            logger.error(f"Error validating token: {e}")
            return None
    
    def extract_token_from_header(self, authorization_header: str) -> Optional[str]:
        """
        Extract JWT token from Authorization header
        
        Args:
            authorization_header: Authorization header value
            
        Returns:
            JWT token string or None if invalid format
        """
        if not authorization_header:
            return None
        
        parts = authorization_header.split()
        if len(parts) != 2 or parts[0].lower() != "bearer":
            return None
        
        return parts[1]

# Global validator instance (will be initialized with environment variables)
_token_validator = None

def get_token_validator() -> Auth0TokenValidator:
    """Get the global token validator instance"""
    global _token_validator
    
    if _token_validator is None:
        domain = os.getenv("AUTH0_DOMAIN")
        audience = os.getenv("AUTH0_AUDIENCE")
        
        if not domain or not audience:
            raise ValueError("AUTH0_DOMAIN and AUTH0_AUDIENCE environment variables must be set")
        
        _token_validator = Auth0TokenValidator(domain, audience)
    
    return _token_validator
