from django.shortcuts import render, redirect
from django.http import HttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.hashers import make_password, check_password
from django.core.mail import send_mail
from django.core.exceptions import ValidationError
from psapp.models import College, NewFaculty
from .utils import rate_limit, validate_email, validate_password, sanitize_html_input
import random, time, json, re, logging, secrets, hmac, threading

logger = logging.getLogger(__name__)

def college_login_view(request):
    return render(request, 'college_login.html')


@rate_limit('college_register', max_attempts=3, window_seconds=1800)  # 3 attempts per 30 minutes
def college_register_api(request):
    if request.method != "POST":
        return JsonResponse({'error': 'POST method required'}, status=405)

    try:
        # 1. SECURITY CHECK: Did they verify the OTP?
        if not request.session.get('email_verified'):
             return JsonResponse({'error': 'Unauthorized: Email OTP not verified.'}, status=403)

        # Check OTP verification time (within 30 minutes)
        verified_time = request.session.get("email_verified_time", 0)
        if (time.time() - verified_time) > 1800:  # 30 minutes
            # Clear expired verification
            for key in ["email_verified", "email_verified_time"]:
                request.session.pop(key, None)
            return JsonResponse({'error': 'OTP verification expired. Please verify again.'}, status=403)

        email = validate_email(request.POST.get('email', ''))
        code = request.POST.get('college_code', '').strip().upper()

        # Verify the session email matches the submission email (prevents swapping email after OTP)
        submitted_email = validate_email(request.POST.get('email', ''))
        if submitted_email != request.session.get('pending_email'):
             return JsonResponse({'error': 'Email mismatch. Please verify again.'}, status=400)

        # Validate college code
        if not code or not re.match(r'^[A-Z0-9]{4,10}$', code):
            return JsonResponse({'error': 'Invalid college code format'}, status=400)

        # Validate other inputs
        college_name = sanitize_html_input(request.POST.get('college_name', ''), 200)
        website = request.POST.get('website', '').strip()
        password = validate_password(request.POST.get('password', ''))

        if not college_name:
            return JsonResponse({'error': 'College name is required'}, status=400)

        # Validate website URL
        if website:
            if not website.startswith(('http://', 'https://')):
                website = 'https://' + website
            url_pattern = r'^https?://[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}(?:/.*)?$'
            if not re.match(url_pattern, website):
                return JsonResponse({'error': 'Invalid website URL'}, status=400)

        # Block Public Email Providers
        domain = email.split('@')[1]
        blocked_keywords = ['yahoo.', 'ymail.', 'rocketmail.', 'outlook.', 'hotmail.', 'live.', 'msn.', 'rediff', 'icloud.', 'aol.']

        if any(keyword in domain for keyword in blocked_keywords):
            return JsonResponse({'error': 'Public emails (gmail, Yahoo, Outlook, etc.) are not allowed. Please use your official college email.'}, status=400)

        # DUPLICATE CHECKS
        if College.objects.filter(college_code=code).exists():
            return JsonResponse({'error': 'College Code already registered.'}, status=400)

        if College.objects.filter(admin_email=email).exists():
            return JsonResponse({'error': 'This email is already registered.'}, status=400)

        # CREATE COLLEGE
        college = College.objects.create(
            college_name=college_name,
            college_code=code,
            admin_email=email,
            website=website,
            password=make_password(password),
            is_verified=True,
            is_approved=True
        )

        # Clean up session
        for key in ["email_verified", "pending_email", "email_verified_time"]:
            request.session.pop(key, None)

        return JsonResponse({'message': 'Registration successful'})

    except ValidationError as e:
        return JsonResponse({'error': str(e)}, status=400)
    except Exception as e:
        logger.exception(f"College registration error: {str(e)}")
        return JsonResponse({'error': 'Registration failed'}, status=500)
  
  
@rate_limit('college_login', max_attempts=5, window_seconds=900)  # 5 attempts per 15 minutes
def college_login_api(request):
    if request.method != "POST": return JsonResponse({'error': 'POST required'}, status=405)

    try:
        email = validate_email(request.POST.get('email', ''))
        password = request.POST.get('password', '')

        if not password:
            return JsonResponse({'error': 'Invalid credentials'}, status=401)

        college = College.objects.get(admin_email=email)
        if check_password(password, college.password):
            # Clear any existing session data
            request.session.flush()

            # Set new session data
            request.session['college_id'] = college.id  # pyright: ignore[reportAttributeAccessIssue]
            request.session['user_type'] = 'college_admin'
            request.session['login_time'] = time.time()

            return HttpResponse("LOGIN_SUCCESS")

        return JsonResponse({'error': 'Invalid credentials'}, status=401)

    except ValidationError:
        return JsonResponse({'error': 'Invalid credentials'}, status=401)
    except College.DoesNotExist:
        return JsonResponse({'error': 'Invalid credentials'}, status=401)
    except Exception as e:
        logger.exception(f"College login error: {str(e)}")
        return JsonResponse({'error': 'Login failed'}, status=500)

# ==========================================
#  COLLEGE FORGOT PASSWORD LOGIC (ACTUAL)
# ==========================================

def college_forgot_otp(request):
    if request.method != "POST":
        return JsonResponse({'error': 'POST method required'}, status=405)
    
    # 1. Get and Clean Email
    email = request.POST.get('email', '').lower().strip()
    
    # 2. Check if College Exists
    try:
        # Check if this email belongs to any college admin
        college = College.objects.get(admin_email=email)
    except College.DoesNotExist:
        # Return 404 so the JS goes to the 'else' block
        return JsonResponse({'error': 'Email not registered as College Admin'}, status=404)

    # 3. Generate OTP
    otp = str(secrets.randbelow(900000) + 100000)
    
    # 4. Save to Session (Temporary Storage)
    request.session['college_fp_email'] = email
    request.session['college_fp_otp'] = otp
    request.session['college_fp_verified'] = False # Reset verification status

    # 5. Send Email
    def send_college_email_bg():
        try:
            send_mail(
                subject="Present Sir - Admin Password Reset",
                message=f"Your OTP for password reset is: {otp}\n\nValid for 10 minutes.",
                from_email="askabhitechnology@gmail.com",
                recipient_list=[email],
                fail_silently=False
            )
        except Exception as e:
            logger.error(f"Mail Error: {str(e)}")

    threading.Thread(target=send_college_email_bg).start()
    return HttpResponse("OTP_SENT") # Text response for success (matches JS)

def college_forgot_verify(request):
    if request.method != "POST":
        return JsonResponse({'error': 'POST required'}, status=405)

    # 1. Get Inputs
    email = request.POST.get('email', '').lower().strip()
    otp = request.POST.get('otp', '').strip()
    
    # 2. Get Session Data
    session_email = request.session.get('college_fp_email')
    session_otp = request.session.get('college_fp_otp')

    # 3. Verify
    if (email and session_email and otp and session_otp and
        hmac.compare_digest(str(email), str(session_email)) and
        hmac.compare_digest(str(otp), str(session_otp))):
        request.session['college_fp_verified'] = True
        return HttpResponse("VERIFIED") # Text response for success
    
    return HttpResponse("INVALID", status=400) # Error triggers JS error handling

def college_reset_pass(request):
    if request.method != "POST":
        return JsonResponse({'error': 'POST required'}, status=405)

    # 1. Security Check: Did they verify OTP?
    if not request.session.get('college_fp_verified'):
        return JsonResponse({'error': 'Unauthorized. Please verify OTP first.'}, status=403)

    new_password = request.POST.get('password')
    email = request.session.get('college_fp_email')

    try:
        # 2. Update Password
        college = College.objects.get(admin_email=email)
        college.password = make_password(new_password) # Hash the password!
        college.save()
        
        # 3. Clean up Session
        for key in ['college_fp_email', 'college_fp_otp', 'college_fp_verified']:
            request.session.pop(key, None)
            
        return HttpResponse("SUCCESS")
    except College.DoesNotExist:
        return JsonResponse({'error': 'User not found'}, status=404)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

def college_logout_view(request):
    request.session.flush() # Clears cookies and session data
    return redirect('psapp:college_login')
