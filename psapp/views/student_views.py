from django.shortcuts import render
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.core.mail import send_mail
from django.db import transaction
from django.db.models import Sum
from psapp.models import NewFaculty, College, Department, Student, Course, AttendanceSession, AttendanceRecord, CollegeNotification
from .utils import invalidate_faculty_dashboard_cache, invalidate_college_dashboard_cache
import json, random, logging, secrets, hmac, threading

logger = logging.getLogger(__name__)


def send_resign_otp(request):
    """Sends OTP to faculty email to confirm leaving college"""
    if request.method != "POST": return JsonResponse({}, status=405)
    
    faculty_id = request.session.get('faculty_id')
    if not faculty_id: return JsonResponse({'error': 'Unauthorized'}, status=401)
    
    try:
        faculty = NewFaculty.objects.get(id=faculty_id)
        if not faculty.department_link:
            return JsonResponse({'error': 'You are not linked to any college.'}, status=400)
            
        otp = str(secrets.randbelow(900000) + 100000)
        request.session['resign_otp'] = otp
        request.session['resign_verified'] = False
        
        def send_resign_email_bg():
            try:
                send_mail(
                    "Confirm Resignation - Present Sir",
                    f"Your OTP to leave your current college is: {otp}\n\nThis will remove your access to all classes immediately.",
                    "askabhitechnology@gmail.com",
                    [faculty.college_email],
                    fail_silently=False
                )
            except Exception as e:
                logger.error(f"Failed to send resign OTP email: {str(e)}")

        threading.Thread(target=send_resign_email_bg).start()
        return JsonResponse({'message': 'OTP sent to your email.'})
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

@csrf_exempt
@transaction.atomic
def leave_college_api(request):
    """Executes resignation if OTP is verified"""
    if request.method != "POST": return JsonResponse({}, status=405)
    
    data = json.loads(request.body)
    user_otp = data.get('otp')
    
    server_otp = request.session.get('resign_otp')
    if not user_otp or not server_otp or not hmac.compare_digest(str(user_otp), str(server_otp)):
        return JsonResponse({'error': 'Invalid OTP'}, status=400)
        
    faculty_id = request.session.get('faculty_id')
    
    try:
        faculty = NewFaculty.objects.get(id=faculty_id)
        college = faculty.department_link.college if faculty.department_link else None
        
        # 1. Unlink Department
        faculty.department_link = None
        faculty.college_name = ""
        faculty.save()
        
        # 2. Orphan their classes (Set faculty=None)
        # We DO NOT delete the classes, just unassign them so history is safe
        Course.objects.filter(faculty=faculty).update(faculty=None, is_assigned=False)
        
        # 3. Notify College Admin
        if college:
            CollegeNotification.objects.create(
                college=college,
                message=f"RESIGNATION: Faculty {faculty.name} has left the college."
            )
            # Clear College Cache so Admin sees the change
            invalidate_college_dashboard_cache(college.id)

        # Clear Faculty Cache
        invalidate_faculty_dashboard_cache(faculty_id)
        
        # Clear Session OTP
        request.session.pop('resign_otp', None)
        
        return JsonResponse({'message': 'You have successfully left the college.'})
        
    except Exception as e:
        logger.exception(f"Resign Error: {e}")
        return JsonResponse({'error': str(e)}, status=500)

def student_portal_view(request):
    return render(request,'student_portal.html')


@csrf_exempt
def public_get_college_depts(request):
    """Step 1: Get Departments using College Code"""
    code = request.GET.get('code', '').strip().upper()
    
    try:
        college = College.objects.get(college_code=code)
        depts = Department.objects.filter(college=college).values('id', 'name')
        
        return JsonResponse({
            'found': True,
            'college_name': college.college_name,
            'departments': list(depts)
        })
    except College.DoesNotExist:
        return JsonResponse({'found': False, 'error': 'Invalid College Code'})

@csrf_exempt
def public_get_student_profile(request):
    """Step 2: Get Full Profile using College Code + Dept + Reg No"""
    if request.method != "POST": return JsonResponse({}, status=405)
    
    try:
        data = json.loads(request.body)
        code = data.get('college_code')
        dept_id = data.get('dept_id')
        reg_no = data.get('reg_no', '').strip()

        # 1. Validate College & Dept
        college = College.objects.get(college_code=code)
        department = Department.objects.get(id=dept_id, college=college)

        # 2. Find Student (Active only)
        student = Student.objects.filter(
            academic_class__department=department,
            reg_no__iexact=reg_no,
            is_active=True
        ).first()

        if not student:
            return JsonResponse({'error': 'Student not found or inactive.'}, status=404)

        # 3. Calculate Attendance
        # FIX: Filter by 'enrolled_students=student' to get ONLY their specific courses
        courses = Course.objects.filter(
            enrolled_students=student, 
            is_active=True
        ).select_related('faculty') # Optimize query
        
        per_course = []
        overall_present = 0
        overall_od = 0
        overall_absent = 0
        overall_total_hours = 0
        overall_total_sessions = 0 # <--- NEW: Track total sessions

        for c in courses:
            # Get sessions for this specific course
            course_sessions = AttendanceSession.objects.filter(course=c)
            sessions_count = course_sessions.count() # Count sessions
            total_hours = course_sessions.aggregate(t=Sum('session_duration'))['t'] or 0
            
            # Get student's specific hours
            # We filter by student object ID for speed and accuracy
            present_h = AttendanceRecord.objects.filter(student=student, session__course=c, status='Present').aggregate(h=Sum('session__session_duration'))['h'] or 0
            od_h = AttendanceRecord.objects.filter(student=student, session__course=c, status='OD').aggregate(h=Sum('session__session_duration'))['h'] or 0
            absent_h = AttendanceRecord.objects.filter(student=student, session__course=c, status='Absent').aggregate(h=Sum('session__session_duration'))['h'] or 0

            attended = present_h + od_h
            pct = round((attended / total_hours) * 100, 1) if total_hours > 0 else 0.0

            per_course.append({
                'subject': c.subject_name,
                'code': c.subject_code,
                'present': present_h,
                'od': od_h,
                'absent': absent_h,
                'total': total_hours,
                'sessions': sessions_count, # Return session count
                'percentage': pct
            })

            overall_present += present_h
            overall_od += od_h
            overall_absent += absent_h
            overall_total_hours += total_hours
            overall_total_sessions += sessions_count

        # 4. Safe Skip Logic
        overall_attended = overall_present + overall_od
        overall_pct = round((overall_attended / overall_total_hours) * 100, 1) if overall_total_hours > 0 else 0.0
        
        required_hours = overall_total_hours * 0.75
        margin = overall_attended - required_hours
        
        status_label = "Safe Zone" if margin >= 0 else "Critical"
        status_color = "green" if margin >= 0 else "red"
        
        return JsonResponse({
            'name': student.name,
            'reg_no': student.reg_no,
            'college_name': college.college_name,
            'dept_name': department.name,
            'academic_year': student.academic_class.academic_year,
            'current_year': student.academic_class.current_year,
            'class_name': student.academic_class.class_name,
            'stats': {
                'overall_pct': overall_pct,
                'total_hours': overall_total_hours,
                'total_sessions': overall_total_sessions, # Sending Total Sessions
                'present': overall_present,
                'od': overall_od,
                'absent': overall_absent,
                'status_label': status_label,
                'status_color': status_color,
                'margin': int(abs(margin))
            },
            'courses': per_course
        })

    except College.DoesNotExist:
        return JsonResponse({'error': 'Invalid College Code'}, status=400)
    except Department.DoesNotExist:
        return JsonResponse({'error': 'Invalid Department'}, status=400)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)    

def promote_class(request):
    class_id = request.POST.get('class_id')
    cls = AcademicClass.objects.get(id=class_id)
    
    if cls.current_year < 4:
        cls.current_year += 1
        cls.save()
        return JsonResponse({'message': f"Promoted to Year {cls.current_year}"})
    else:
        # Move to 'Alumni' or archive
        return JsonResponse({'message': "Class Graduated!"})
