import json
import hmac
import hashlib
import base64
import time
from django.conf import settings
from django.core.exceptions import ValidationError

class JWTError(Exception):
    pass

class JWT:
    """
    Simple JWT implementation using HMAC-SHA256
    Note: For production, consider using djangorestframework-simplejwt
    """

    @staticmethod
    def encode(payload, secret=None, algorithm=None):
        """Encode payload into JWT token"""
        if secret is None:
            secret = settings.JWT_SECRET_KEY
        if algorithm is None:
            algorithm = settings.JWT_ALGORITHM

        # Create header
        header = {
            'alg': algorithm,
            'typ': 'JWT'
        }

        # Add issued at and expiration
        now = int(time.time())
        payload_copy = payload.copy()
        payload_copy['iat'] = now
        if 'exp' not in payload_copy:
            payload_copy['exp'] = now + settings.JWT_ACCESS_TOKEN_LIFETIME

        # Encode header and payload
        header_b64 = base64.urlsafe_b64encode(
            json.dumps(header).encode()
        ).decode().rstrip('=')

        payload_b64 = base64.urlsafe_b64encode(
            json.dumps(payload_copy).encode()
        ).decode().rstrip('=')

        # Create signature
        message = f"{header_b64}.{payload_b64}"
        signature = hmac.new(
            secret.encode(),
            message.encode(),
            hashlib.sha256
        ).digest()

        signature_b64 = base64.urlsafe_b64encode(signature).decode().rstrip('=')

        return f"{header_b64}.{payload_b64}.{signature_b64}"

    @staticmethod
    def decode(token, secret=None, verify_expiration=True):
        """Decode and verify JWT token"""
        if secret is None:
            secret = settings.JWT_SECRET_KEY

        try:
            # Split token
            parts = token.split('.')
            if len(parts) != 3:
                raise JWTError("Invalid token format")

            header_b64, payload_b64, signature_b64 = parts

            # Decode payload
            payload_json = base64.urlsafe_b64decode(payload_b64 + '===')
            payload = json.loads(payload_json.decode())

            # Verify signature
            message = f"{header_b64}.{payload_b64}"
            expected_signature = hmac.new(
                secret.encode(),
                message.encode(),
                hashlib.sha256
            ).digest()

            provided_signature = base64.urlsafe_b64decode(signature_b64 + '===')

            if not hmac.compare_digest(expected_signature, provided_signature):
                raise JWTError("Invalid signature")

            # Check expiration
            if verify_expiration:
                now = time.time()
                if payload.get('exp', 0) < now:
                    raise JWTError("Token expired")

            return payload

        except (json.JSONDecodeError, ValueError) as e:
            raise JWTError(f"Invalid token: {str(e)}")

def create_access_token(user_id, user_type):
    """Create JWT access token for user"""
    payload = {
        'user_id': user_id,
        'user_type': user_type,
        'token_type': 'access'
    }
    return JWT.encode(payload)

def create_refresh_token(user_id, user_type):
    """Create JWT refresh token for user"""
    payload = {
        'user_id': user_id,
        'user_type': user_type,
        'token_type': 'refresh',
        'exp': int(time.time()) + settings.JWT_REFRESH_TOKEN_LIFETIME
    }
    return JWT.encode(payload)

def verify_token(token):
    """Verify JWT token and return payload"""
    try:
        return JWT.decode(token)
    except JWTError:
        return None

def refresh_access_token(refresh_token):
    """Create new access token from valid refresh token"""
    payload = verify_token(refresh_token)
    if not payload or payload.get('token_type') != 'refresh':
        return None

    # Create new access token
    return create_access_token(payload['user_id'], payload['user_type'])



