from django.shortcuts import render, redirect
from django.http import HttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.core.mail import send_mail
from django.contrib.auth.hashers import make_password, check_password
from django.db import IntegrityError
from django.core.cache import cache
from django.core.exceptions import ValidationError
from datetime import datetime
from psapp.models import NewFaculty, College, Department, Student
from .utils import rate_limit, validate_email, validate_password, validate_name, sanitize_html_input
from ..jwt_utils import create_access_token, create_refresh_token, refresh_access_token # relative import
import random, time, json, logging, secrets, hmac, threading, re
from django.conf import settings

logger = logging.getLogger(__name__)

# ==========================================
@csrf_exempt
#  AUTH & BASIC VIEWS
# ==========================================
def index_view(request):
    # 1. Get raw counts
    c_count = College.objects.count()
    d_count = Department.objects.count()
    f_count = NewFaculty.objects.count()
    s_count = Student.objects.filter(academic_class__isnull=False).count()

    # 2. Helper function for "K" formatting (1200 -> 1.2K)
    def format_number(num):
        if num >= 1000000:
            return f"{num/1000000:.1f}M"
        if num >= 1000:
            return f"{num/1000:.1f}K"
        return str(num)

    context = {
        'college_count': format_number(c_count),
        'dept_count': format_number(d_count),
        'faculty_count': format_number(f_count),
        'student_count': format_number(s_count),
        
        # We also pass raw numbers for the JavaScript counter animation to work correctly
        'raw_c_count': c_count,
        'raw_d_count': d_count,
        'raw_f_count': f_count,
        'raw_s_count': s_count,
    }
    return render(request, 'index.html', context)

@rate_limit('faculty_login', max_attempts=5, window_seconds=900)  # 5 attempts per 15 minutes
def login(request):
    if request.method == "POST":
        try:
            email = validate_email(request.POST.get("email", ""))
            password = request.POST.get("password", "")

            if not password:
                return HttpResponse("INVALID")

            logger.debug(f"Login attempt: {email}")

            user = NewFaculty.objects.get(college_email=email)
            if not check_password(password, user.password):
                logger.warning(f"Wrong password for {email}")
                return HttpResponse("INVALID")

            if not user.is_verified:
                logger.warning(f"User not verified: {email}")
                return HttpResponse("NOT_VERIFIED")

            # Clear any existing session data
            request.session.flush()

            # Set new session data
            request.session['faculty_id'] = user.id  # pyright: ignore[reportAttributeAccessIssue]
            request.session['user_type'] = 'faculty'
            request.session['login_time'] = time.time()

            return HttpResponse("LOGIN_SUCCESS")

        except (ValidationError, ValueError) as e:
            logger.warning(f"Invalid login input: {str(e)}")
            return HttpResponse("INVALID")
        except NewFaculty.DoesNotExist:
            logger.warning(f"Login failed. Email not registered: {email}")
            return HttpResponse("INVALID")
        except Exception as e:
            logger.exception(f"Unexpected login error: {str(e)}")
            return HttpResponse("INVALID")

    return render(request, "login.html")

@rate_limit('send_otp', max_attempts=3, window_seconds=600)  # 3 attempts per 10 minutes
def send_otp(request):
    if request.method == "POST":
        try:
            email = validate_email(request.POST.get("email", ""))

            # Check if College Admin flow or Faculty flow
            req_type = request.POST.get('type')

            # Simple Faculty Logic
            if not req_type and NewFaculty.objects.filter(college_email=email).exists():
                return HttpResponse("EMAIL_EXISTS")

            otp = str(secrets.randbelow(900000) + 100000)

            def send_email_bg():
                try:
                    send_mail(
                        "Present Sir!!! - OTP Verification",
                        f"Your OTP is: {otp}\n\nThis OTP will expire in 10 minutes.",
                        "presentsirtechnologies@gmail.com",
                        [email],
                        fail_silently=False
                    )
                except Exception as e:
                    logger.exception(f"Failed to send OTP email to {email}: {str(e)}")

            threading.Thread(target=send_email_bg).start()

            # Clear any existing OTP data
            for key in ["pending_email", "pending_otp", "otp_timestamp"]:
                request.session.pop(key, None)

            request.session["pending_email"] = email
            request.session["pending_otp"] = otp
            request.session["otp_timestamp"] = time.time()

            return HttpResponse("OTP_SENT")

        except ValidationError as e:
            logger.warning(f"Invalid email for OTP: {str(e)}")
            return HttpResponse("INVALID_EMAIL")
        except Exception as e:
            logger.exception(f"Unexpected error sending OTP: {str(e)}")
            return HttpResponse("EMAIL_ERROR")

def verify_email_otp(request):
    try:
        email = validate_email(request.POST.get("email", ""))
        otp = request.POST.get("otp", "").strip()

        if not otp or len(otp) != 6 or not otp.isdigit():
            return HttpResponse("INVALID")

        # Check OTP expiration (10 minutes)
        otp_timestamp = request.session.get("otp_timestamp")
        if otp_timestamp and (time.time() - otp_timestamp) > 600:  # 10 minutes
            # Clear expired OTP data
            for key in ["pending_email", "pending_otp", "otp_timestamp"]:
                request.session.pop(key, None)
            return HttpResponse("EXPIRED")

        pending_email = request.session.get("pending_email")
        pending_otp = request.session.get("pending_otp")
        if (pending_email and pending_otp and
            hmac.compare_digest(str(email), str(pending_email)) and
            hmac.compare_digest(str(otp), str(pending_otp))):
            request.session["email_verified"] = True
            request.session["email_verified_time"] = time.time()
            return HttpResponse("VERIFIED")

        return HttpResponse("WRONG")

    except ValidationError:
        return HttpResponse("INVALID")
    except Exception as e:
        logger.exception(f"Unexpected error verifying email OTP: {str(e)}")
        return HttpResponse("INVALID")

def register(request):
    if request.method == "POST":
        try:
            # Verify OTP was recently verified (within 30 minutes)
            if not request.session.get("email_verified"):
                return HttpResponse("OTP_NOT_VERIFIED")

            verified_time = request.session.get("email_verified_time", 0)
            if (time.time() - verified_time) > 1800:  # 30 minutes
                # Clear expired verification
                for key in ["email_verified", "email_verified_time"]:
                    request.session.pop(key, None)
                return HttpResponse("OTP_EXPIRED")

            # Validate all inputs
            name = validate_name(request.POST.get("name", ""))
            college_name = sanitize_html_input(request.POST.get("college_name", ""), 150)
            department = sanitize_html_input(request.POST.get("department", ""), 100)
            designation = sanitize_html_input(request.POST.get("designation", ""), 50)
            mobile_num = request.POST.get("mobile_num", "").strip()
            raw_password = validate_password(request.POST.get("password", ""))

            clean_mobile = re.sub(r'[^0-9]', '', mobile_num) 
            # Check length (usually 10-15 digits)
            if not clean_mobile or len(clean_mobile) < 10 or len(clean_mobile) > 15:
                print(f"Error: Invalid Mobile Number: '{mobile_num}' -> Cleaned: '{clean_mobile}'")
                return HttpResponse("INVALID_MOBILE")

            # Check if email is still pending (not used by someone else)
            pending_email = request.session.get("pending_email")
            if NewFaculty.objects.filter(college_email=pending_email).exists():
                return HttpResponse("EMAIL_EXISTS")

            # Generate unique faculty registration ID
            while True:
                unique_id = f"PS-FAC-{int(time.time())}{random.randint(100, 999)}"
                if not NewFaculty.objects.filter(faculty_reg_id=unique_id).exists():
                    break

            try:
                NewFaculty.objects.create(
                    faculty_reg_id=unique_id,
                    college_name=college_name,
                    name=name,
                    department=department,
                    designation=designation,
                    college_email=pending_email,
                    mobile_num=mobile_num,
                    password=make_password(raw_password),
                    is_verified=True
                )
            except IntegrityError:
                # If unique constraint fails (extremely rare), try one more time with new ID
                unique_id = f"PS-FAC-{int(time.time())}{random.randint(1000, 9999)}"
                NewFaculty.objects.create(
                    faculty_reg_id=unique_id,
                    college_name=college_name,
                    name=name,
                    department=department,
                    designation=designation,
                    college_email=pending_email,
                    mobile_num=mobile_num,
                    password=make_password(raw_password),
                    is_verified=True
                )

            # Clear session data
            for key in ["pending_email", "pending_otp", "email_verified", "email_verified_time", "otp_timestamp"]:
                request.session.pop(key, None)

            return HttpResponse("REGISTERED")

        except ValidationError as e:
            logger.warning(f"Validation error during registration: {str(e)}")
            return HttpResponse(f"VALIDATION_ERROR: {str(e)}")
        except Exception as e:
            logger.exception(f"Registration failed: {str(e)}")
            return HttpResponse(f"REGISTER_FAIL: {str(e)}")

# --- Password Reset Logic ---
def forgot_send_otp(request):
    if request.method != "POST": return HttpResponse("ONLY_POST_ALLOWED")
    email = (request.POST.get("email") or "").lower().strip()
    
    if not email:
        return HttpResponse("INVALID_EMAIL")
    
    try:
        user = NewFaculty.objects.get(college_email=email)
    except NewFaculty.DoesNotExist:
        return HttpResponse("NO_EMAIL")

    otp = str(secrets.randbelow(900000) + 100000)
    # FIX: Add rate limiting and timestamp for OTP race condition prevention
    cache_key = f"otp_attempt:{email}"
    attempt_count = cache.get(cache_key, 0)
    
    if attempt_count >= 3:
        return HttpResponse("OTP_RATE_LIMIT_EXCEEDED")
    
    # FIX: Store OTP with expiry in cache + timestamp instead of session only
    cache_key_otp = f"otp_reset:{email}"
    cache_key_time = f"otp_time:{email}"
    
    cache.set(cache_key_otp, otp, 600)  # 10 minutes expiry
    cache.set(cache_key_time, datetime.now().isoformat(), 600)
    cache.set(cache_key, attempt_count + 1, 300)  # Rate limit window: 5 minutes
    
    request.session["fp_email"] = email  # Keep for reference
    request.session["fp_otp"] = otp  # Backup in session
    
    def send_forgot_email_bg():
        try:
            send_mail("Password Reset", f"OTP: {otp}", "presentsirtechnologies@gmail.com", [email])
        except Exception as e:
            logger.exception(f"Failed to send password reset email to {email}: {str(e)}")

    threading.Thread(target=send_forgot_email_bg).start()
    return HttpResponse("FP_OTP_SENT")

def forgot_verify_otp(request):
    email = (request.POST.get("email") or "").lower().strip()
    otp = request.POST.get("otp")
    
    if not email or not otp:
        return HttpResponse("FP_WRONG")
    
    # FIX: Verify with cache timestamp to prevent timing attacks
    cache_key_otp = f"otp_reset:{email}"
    cache_key_time = f"otp_time:{email}"
    cached_otp = cache.get(cache_key_otp)
    otp_timestamp = cache.get(cache_key_time)
    
    # Check if OTP exists and is not expired
    if not cached_otp or not otp_timestamp:
        return HttpResponse("FP_OTP_EXPIRED")
    
    # Check timestamp (should be within 10 minutes)
    otp_time = datetime.fromisoformat(otp_timestamp)
    if (datetime.now() - otp_time).total_seconds() > 600:
        cache.delete(cache_key_otp)
        cache.delete(cache_key_time)
        return HttpResponse("FP_OTP_EXPIRED")
    
    # Verify OTP (use constant-time comparison to prevent timing attacks)
    if cached_otp and hmac.compare_digest(str(otp), str(cached_otp)):
        request.session["fp_verified"] = True
        request.session["fp_email"] = email
        # Clear OTP after verification
        cache.delete(cache_key_otp)
        cache.delete(cache_key_time)
        return HttpResponse("FP_VERIFIED")
    
    return HttpResponse("FP_WRONG")

def reset_password(request):
    if request.method == "POST" and request.session.get("fp_verified"):
        email = request.session.get("fp_email")
        user = NewFaculty.objects.get(college_email=email)
        user.password = make_password(request.POST.get("password"))
        user.save()
        return HttpResponse("PASSWORD_RESET")
    return HttpResponse("NOT_ALLOWED")

def logout_view(request):
    request.session.flush()
    return redirect('psapp:login')
# JWT Authentication Endpoints (Alternative to Session-based auth)
@csrf_exempt
@rate_limit('jwt_login', max_attempts=5, window_seconds=900)
def jwt_login_api(request):
    """
    JWT-based login endpoint that returns access and refresh tokens
    """
    if request.method != "POST":
        return JsonResponse({'error': 'POST method required'}, status=405)

    try:
        data = json.loads(request.body)
        email = validate_email(data.get('email', ''))
        password = data.get('password', '')

        if not password:
            return JsonResponse({'error': 'Password is required'}, status=400)

        # Try faculty login
        try:
            user = NewFaculty.objects.get(college_email=email)
            user_type = 'faculty'
            user_id = user.id
        except NewFaculty.DoesNotExist:
            # Try college admin login
            try:
                college = College.objects.get(admin_email=email)
                if check_password(password, college.password):
                    user_type = 'college_admin'
                    user_id = college.id
                else:
                    return JsonResponse({'error': 'Invalid credentials'}, status=401)
            except College.DoesNotExist:
                return JsonResponse({'error': 'Invalid credentials'}, status=401)
        else:
            # Faculty login
            if not check_password(password, user.password):
                return JsonResponse({'error': 'Invalid credentials'}, status=401)

            if not user.is_verified:
                return JsonResponse({'error': 'Account not verified'}, status=401)

        # Create tokens
        access_token = create_access_token(user_id, user_type)
        refresh_token = create_refresh_token(user_id, user_type)

        return JsonResponse({
            'access_token': access_token,
            'refresh_token': refresh_token,
            'token_type': 'Bearer',
            'expires_in': settings.JWT_ACCESS_TOKEN_LIFETIME,
            'user_type': user_type
        })

    except ValidationError as e:
        return JsonResponse({'error': str(e)}, status=400)
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)
    except Exception as e:
        logger.exception(f"JWT login error: {str(e)}")
        return JsonResponse({'error': 'Login failed'}, status=500)

@csrf_exempt
def jwt_refresh_api(request):
    """
    Refresh access token using refresh token
    """
    if request.method != "POST":
        return JsonResponse({'error': 'POST method required'}, status=405)

    try:
        data = json.loads(request.body)
        refresh_token = data.get('refresh_token')

        if not refresh_token:
            return JsonResponse({'error': 'Refresh token required'}, status=400)

        # Verify refresh token and create new access token
        access_token = refresh_access_token(refresh_token)
        if not access_token:
            return JsonResponse({'error': 'Invalid or expired refresh token'}, status=401)

        return JsonResponse({
            'access_token': access_token,
            'token_type': 'Bearer',
            'expires_in': settings.JWT_ACCESS_TOKEN_LIFETIME
        })

    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)
    except Exception as e:
        logger.exception(f"JWT refresh error: {str(e)}")
        return JsonResponse({'error': 'Token refresh failed'}, status=500)