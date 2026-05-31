from functools import wraps
from django.core.cache import cache
from django.http import HttpResponse
from django.conf import settings
from django.core.exceptions import ValidationError
import json, re, html, logging

logger = logging.getLogger(__name__)

class HttpResponseTooManyRequests(HttpResponse):
    status_code = 429
    
# Rate limiting decorator
def rate_limit(key_prefix, max_attempts=5, window_seconds=300):
    """
    Rate limiting decorator
    key_prefix: unique identifier for the rate limit (e.g., 'login', 'otp')
    max_attempts: maximum attempts allowed in the window
    window_seconds: time window in seconds (default 5 minutes)
    """
    def decorator(view_func):
        @wraps(view_func)
        def _wrapped_view(request, *args, **kwargs):
            if getattr(settings, 'DEBUG', False):
                return view_func(request, *args, **kwargs)

            # Get client identifier (IP address)
            client_ip = request.META.get('HTTP_X_FORWARDED_FOR', request.META.get('REMOTE_ADDR', '')).split(',')[0].strip()

            # Create cache key
            cache_key = f"rate_limit:{key_prefix}:{client_ip}"

            # Get current attempts
            attempts = cache.get(cache_key, 0)

            if attempts >= max_attempts:
                return HttpResponseTooManyRequests(
                    json.dumps({
                        'error': f'Too many attempts. Please try again in {window_seconds//60} minutes.'
                    }),
                    content_type='application/json',
                    status=429
                )

            # Increment attempts
            cache.set(cache_key, attempts + 1, window_seconds)

            return view_func(request, *args, **kwargs)
        return _wrapped_view
    return decorator

# Input validation and sanitization functions
def validate_email(email):
    """Validate email format and length"""
    if not email or len(email) > 254:
        raise ValidationError("Invalid email length")

    email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    if not re.match(email_pattern, email):
        raise ValidationError("Invalid email format")

    return html.escape(email.strip().lower())

def validate_password(password):
    """Validate password strength"""
    if not password or len(password) < 8:
        raise ValidationError("Password must be at least 8 characters long")

    if len(password) > 128:
        raise ValidationError("Password too long")

    # Check for at least one uppercase, one lowercase, one digit
    if not re.search(r'[A-Z]', password):
        raise ValidationError("Password must contain at least one uppercase letter")

    if not re.search(r'[a-z]', password):
        raise ValidationError("Password must contain at least one lowercase letter")

    if not re.search(r'\d', password):
        raise ValidationError("Password must contain at least one digit")

    return password

def validate_name(name):
    """Validate and sanitize name input"""
    if not name or len(name) > 100:
        raise ValidationError("Invalid name length")

    # Allow only letters, spaces, hyphens, apostrophes
    if not re.match(r"^[a-zA-Z\s\-']+$", name):
        raise ValidationError("Name contains invalid characters")

    return html.escape(name.strip())

def validate_reg_no(reg_no):
    """Validate registration number format"""
    if not reg_no or len(reg_no) > 50:
        raise ValidationError("Invalid registration number length")

    # Allow alphanumeric, hyphens, underscores
    if not re.match(r'^[a-zA-Z0-9\-_]+$', reg_no):
        raise ValidationError("Registration number contains invalid characters")

    return html.escape(reg_no.strip().upper())

def sanitize_html_input(input_string, max_length=1000):
    """Sanitize HTML input and validate length"""
    if not input_string:
        return ""

    if len(input_string) > max_length:
        raise ValidationError(f"Input too long (max {max_length} characters)")
    return html.escape(input_string.strip())

# Cache management utilities
def invalidate_faculty_dashboard_cache(faculty_id):
    """Invalidate faculty dashboard cache"""
    if faculty_id:
        try:
            cache.delete(f"faculty_dashboard:{faculty_id}")
        except Exception as e:
            logger.warning(f"Failed to invalidate faculty cache for {faculty_id}: {str(e)}")

def invalidate_college_dashboard_cache(college_id):
    """Invalidate college dashboard cache"""
    if college_id:
        try:
            cache.delete(f"college_dashboard:{college_id}")
        except Exception as e:
            logger.warning(f"Failed to invalidate college cache for {college_id}: {str(e)}")

def invalidate_user_caches(request):
    """Invalidate all relevant caches for the current user"""
    faculty_id = request.session.get('faculty_id')
    college_id = request.session.get('college_id')

    invalidate_faculty_dashboard_cache(faculty_id)
    invalidate_college_dashboard_cache(college_id)
