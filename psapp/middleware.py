import time
import logging
from django.conf import settings
from django.http import JsonResponse
from django.shortcuts import redirect
from .jwt_utils import verify_token

logger = logging.getLogger(__name__)

class SessionSecurityMiddleware:
    """
    Middleware for enhanced session security and management
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Check for JWT token in Authorization header
        auth_header = request.META.get('HTTP_AUTHORIZATION', '')
        if auth_header.startswith('Bearer '):
            token = auth_header[7:]  # Remove 'Bearer ' prefix
            self._authenticate_jwt(request, token)

        # Check session expiration for authenticated users
        if hasattr(request, 'session') and request.session.session_key:
            self._check_session_expiry(request)
            self._check_session_integrity(request)

        response = self.get_response(request)

        # Add security headers
        self._add_security_headers(response)

        return response

    def _authenticate_jwt(self, request, token):
        """Authenticate user using JWT token"""
        try:
            payload = verify_token(token)
            if payload:
                # Set user information in request for views to use
                # DO NOT set session variables to avoid bypassing session expiration
                request.jwt_user = {
                    'user_id': payload['user_id'],
                    'user_type': payload['user_type'],
                    'token_type': payload['token_type']
                }
                # JWT users are authenticated but don't interfere with session checks

        except Exception as e:
            logger.warning(f"JWT authentication failed: {str(e)}")
            # Don't set any user info if token is invalid

    def _check_session_expiry(self, request):
        """Check if session has expired based on custom timeout"""
        login_time = request.session.get('login_time')
        if login_time:
            # Custom session timeout (1 hour)
            session_timeout = getattr(settings, 'SESSION_TIMEOUT_SECONDS', 3600)
            if (time.time() - login_time) > session_timeout:
                logger.warning(f"Session expired for user type: {request.session.get('user_type', 'unknown')}")
                request.session.flush()
                # Return early for API requests
                if request.path.startswith('/api/') or request.path.startswith('/college/'):
                    # This will be handled by the view, but we log it
                    pass

    def _check_session_integrity(self, request):
        """Check for session tampering indicators"""
        user_type = request.session.get('user_type')
        faculty_id = request.session.get('faculty_id')
        college_id = request.session.get('college_id')

        # Ensure only one user type is set
        if user_type == 'faculty' and college_id:
            logger.warning("Session integrity violation: faculty user has college_id")
            request.session.flush()
        elif user_type == 'college_admin' and faculty_id:
            logger.warning("Session integrity violation: college admin has faculty_id")
            request.session.flush()

    def _add_security_headers(self, response):
        """Add security headers to response"""
        response['X-Content-Type-Options'] = 'nosniff'
        response['X-Frame-Options'] = 'DENY'
        response['X-XSS-Protection'] = '1; mode=block'

        # Only add HSTS in production (when DEBUG=False)
        if not getattr(settings, 'DEBUG', True):
            response['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'

        return response



