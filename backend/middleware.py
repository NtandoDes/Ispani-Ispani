# middleware.py - Create this file in your app directory
import jwt
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from django.conf import settings
from channels.middleware import BaseMiddleware
from channels.db import database_sync_to_async
from urllib.parse import parse_qs
import logging

logger = logging.getLogger(__name__)
User = get_user_model()

@database_sync_to_async
def get_user_by_token(token):
    """Get user from JWT token"""
    try:
        # Decode the token
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=['HS256'])
        user_id = payload.get('user_id')
        
        if user_id:
            user = User.objects.get(id=user_id)
            return user
    except jwt.ExpiredSignatureError:
        logger.warning("JWT token has expired")
    except jwt.InvalidTokenError:
        logger.warning("Invalid JWT token")
    except User.DoesNotExist:
        logger.warning(f"User with id {user_id} does not exist")
    except Exception as e:
        logger.error(f"Error decoding JWT token: {e}")
    
    return AnonymousUser()

@database_sync_to_async
def get_user_by_session(session_key):
    """Get user from Django session"""
    try:
        from django.contrib.sessions.models import Session
        from django.contrib.auth import get_user_model
        
        session = Session.objects.get(session_key=session_key)
        uid = session.get_decoded().get('_auth_user_id')
        
        if uid:
            user = User.objects.get(pk=uid)
            return user
    except (Session.DoesNotExist, User.DoesNotExist, Exception) as e:
        logger.warning(f"Error getting user from session: {e}")
    
    return AnonymousUser()

class TokenAuthMiddleware(BaseMiddleware):
    """Custom middleware for token authentication"""
    
    async def __call__(self, scope, receive, send):
        # Get token from query parameters or headers
        token = None
        
        # Try to get token from query parameters
        query_params = parse_qs(scope.get("query_string", b"").decode())
        if "token" in query_params:
            token = query_params["token"][0]
        
        # Try to get token from headers
        if not token:
            headers = dict(scope.get("headers", []))
            if b"authorization" in headers:
                auth_header = headers[b"authorization"].decode()
                if auth_header.startswith("Bearer "):
                    token = auth_header[7:]  # Remove "Bearer " prefix
        
        # Try to get session key from cookies
        session_key = None
        if b"cookie" in dict(scope.get("headers", [])):
            cookie_header = dict(scope.get("headers", []))[b"cookie"].decode()
            # Parse sessionid from cookie
            for cookie in cookie_header.split(";"):
                if "sessionid=" in cookie:
                    session_key = cookie.split("sessionid=")[1].strip()
                    break
        
        # Authenticate user
        user = AnonymousUser()
        
        if token:
            user = await get_user_by_token(token)
        elif session_key:
            user = await get_user_by_session(session_key)
        
        # Add user to scope
        scope["user"] = user
        
        return await super().__call__(scope, receive, send)

# For session-based authentication (alternative approach)
class SessionAuthMiddleware(BaseMiddleware):
    """Session-based authentication middleware"""
    
    async def __call__(self, scope, receive, send):
        # This is for session-based auth - you might need to install channels-redis
        from channels.sessions import SessionMiddleware
        from channels.auth import AuthMiddleware
        
        # Apply session and auth middleware
        scope = await SessionMiddleware(scope, receive, send)
        scope = await AuthMiddleware(scope, receive, send)
        
        return await super().__call__(scope, receive, send)