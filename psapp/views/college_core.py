from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.db import transaction
from django.db.models import Sum
from django.core.cache import cache
from psapp.models import College, Department, NewFaculty, AcademicClass, Student, CollegeNotification, Course, FacultyNotification,AttendanceSession,AttendanceRecord
from .utils import invalidate_college_dashboard_cache, invalidate_faculty_dashboard_cache
import json, logging

logger = logging.getLogger(__name__)

def college_dashboard_view(request):
    college_id = request.session.get('college_id')
    if not college_id: return redirect('psapp:college_login')
    return render(request, 'college_dashboard.html', {'college': get_object_or_404(College, id=college_id)})

@csrf_exempt
def get_college_dashboard_data(request):
    college_id = request.session.get('college_id')
    # Also check JWT authentication
    jwt_user = getattr(request, 'jwt_user', None)
    if jwt_user and jwt_user['user_type'] == 'college_admin':
        college_id = jwt_user['user_id']

    if not college_id:
        return redirect('psapp:college_login')

    # Cache key for college dashboard (cache for 10 minutes)
    cache_key = f"college_dashboard:{college_id}"
    cached_data = cache.get(cache_key)

    if cached_data:
        return JsonResponse(cached_data)
    
    college = College.objects.get(id=college_id)

    # Optimize queries with prefetch_related and select_related
    departments = Department.objects.filter(college=college).prefetch_related(
        'classes',  # Prefetch all classes for each department
        'faculty_members'  # Prefetch faculty for each department
    )

    # 1. Fetch Departments & Classes (Optimized)
    dept_data = []
    for dept in departments:
        # Classes are already prefetched
        academic_classes = dept.classes.all()
        classes_list = [{'id': c.id,
                         'name': c.class_name, 
                         'section': c.section, 
                         'batch': c.academic_year, 
                         'year': c.current_year,
                         'semester': c.current_semester
                         } for c in academic_classes]  # pyright: ignore[reportAttributeAccessIssue]

        dept_data.append({
            'id': dept.id, 'name': dept.name, 'year': dept.established_year,  # pyright: ignore[reportAttributeAccessIssue]
            'classCount': len(classes_list),  # Use list length instead of count()
            'facultyCount': len(dept.faculty_members.all()),  # Use prefetched data
            'classes': classes_list
        })

    # 2. NEW: Fetch All Verified Faculty for this College (Paginated)
    all_faculty = NewFaculty.objects.filter(department_link__college=college).select_related('department_link')
    total_faculty = all_faculty.count()
    
    # Implement pagination: default to page 1, 50 items per page
    try:
        page = int(request.GET.get('page', 1))
        limit = int(request.GET.get('limit', 50))
        if page < 1: page = 1
        if limit < 1 or limit > 100: limit = 50
    except (TypeError, ValueError):
        page = 1
        limit = 50

    start_idx = (page - 1) * limit
    end_idx = start_idx + limit
    paginated_faculty = all_faculty[start_idx:end_idx]
    
    faculty_list = []
    for f in paginated_faculty:
        faculty_list.append({
            'id': f.id, # pyright: ignore[reportAttributeAccessIssue]
            'name': f.name,
            'designation': f.designation,
            'department': f.department_link.name if f.department_link else "Unassigned",
            'email': f.college_email,
            'mobile': f.mobile_num,
            'photo': f.profile_photo.url if f.profile_photo else None,
            'reg_id': f.faculty_reg_id
        })

    response_data = {
        'departments': dept_data,
        'faculty': faculty_list, # <--- SENDING THIS NOW
        'stats': {
            'total_depts': len(dept_data),  # Use list length instead of count()
            'total_faculty': total_faculty,
            'page': page,
            'limit': limit
        }
    }

    # Cache the response for 10 minutes
    cache.set(cache_key, response_data, 600)  # 10 minutes

    return JsonResponse(response_data)

def add_department_api(request):
    """Creates Department ONLY if OTP was verified"""
    if request.method != "POST": return JsonResponse({'error': 'POST required'}, status=405)
    
    # 1. SECURITY CHECK
    if not request.session.get('add_dept_verified'):
        return JsonResponse({'error': 'Unauthorized: OTP verification required.'}, status=403)

    try:
        college_id = request.session.get('college_id')
        name = request.POST.get('name')
        year = request.POST.get('year')

        # 2. Duplicate Check
        if Department.objects.filter(college_id=college_id, name__iexact=name).exists():
             return JsonResponse({'error': f"Department '{name}' already exists."}, status=400)

        # 3. Create
        Department.objects.create(
            college_id=college_id,
            name=name,
            established_year=year
        )
        invalidate_college_dashboard_cache(college_id)
        # 4. Reset Verification (One-time use)
        request.session['add_dept_verified'] = False
        request.session['add_dept_otp'] = None
        
        return JsonResponse({'message': 'Department Created Successfully'})
        
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

@csrf_exempt
@transaction.atomic
def add_academic_class_api(request):
    if request.method != "POST": 
        return JsonResponse({'error': 'POST required'}, status=405)
    
    try:
        data = json.loads(request.body)
        dept_id = data.get('dept_id')
        name = data.get('name').strip()
        section = data.get('section', 'A').strip().upper()
        batch = data.get('acad_year') # "2025-2029"
        college_id = request.session.get('college_id')
        
        # We need the college object for the Student Foreign Key
        college = College.objects.get(id=college_id)

        # 1. NEW DUPLICATE CHECK: Class Name must be unique within a Department
        if AcademicClass.objects.filter(
            department_id=dept_id, 
            class_name__iexact=name
        ).exists():
            return JsonResponse({'error': f"Class '{name}' already exists in this department!"}, status=400)

        # 2. Validate Students (Batch Check for Duplicates in College)
        new_students_data = data.get('students', [])
        incoming_regs = [s['regNo'].strip().upper() for s in new_students_data]
        
        existing_regs = Student.objects.filter(
            college=college, 
            reg_no__in=incoming_regs
        ).values_list('reg_no', flat=True)
    
        if existing_regs:
            return JsonResponse({
                'error': f'The following Register Numbers already exist in your college: {list(existing_regs)}'
            }, status=400)

        # 3. CREATE THE ACADEMIC CLASS (This was missing in your snippet)
        # We default to Semester 1 / Year 1 on creation
        curr_year = int(data.get('currentYear', 1))
        
        new_class = AcademicClass.objects.create(
            department_id=dept_id,
            class_name=name,
            section=section,
            academic_year=batch,
            current_year=curr_year,
            current_semester= (curr_year * 2) - 1, # Default logic: Year 1 = Sem 1, Year 2 = Sem 3
            is_active=True
        )

        # 4. CREATE STUDENTS LINKED TO THIS CLASS
        students_to_create = []
        for s in new_students_data:
            students_to_create.append(Student(
                college=college, # Link to College (Master Scope)
                academic_class=new_class, # Link to the Class created above
                name=s['name'],
                reg_no=s['regNo'].strip().upper(),
                email=s.get('email', '')
            ))
        
        Student.objects.bulk_create(students_to_create)

        invalidate_college_dashboard_cache(college_id)

        return JsonResponse({'message': 'Class created successfully'})

    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON data provided'}, status=400)
    except College.DoesNotExist:
        return JsonResponse({'error': 'College session invalid'}, status=401)
    except Exception as e:
        logger.exception(f"Unexpected error creating academic class: {str(e)}")
        return JsonResponse({'error': f'An unexpected error occurred: {str(e)}'}, status=500)

@csrf_exempt
def search_faculty_api(request):
    query = request.GET.get('q', '').lower()
    faculties = NewFaculty.objects.filter(college_email__icontains=query)[:5]
    return JsonResponse({'results': [{'id': f.id, 'name': f.name, 'email': f.college_email} for f in faculties]}) # pyright: ignore[reportAttributeAccessIssue]

def add_student_to_class_api(request):
    return JsonResponse({'message': 'Student Added'})

def get_college_notifications_api(request):
    college_id = request.session.get('college_id')
    if not college_id: return JsonResponse({'error': 'Unauthorized'}, status=401)
    
    notifs = CollegeNotification.objects.filter(college_id=college_id, is_read=False).order_by('-created_at')
    
    data = [{'id': n.id, 'message': n.message, 'date': n.created_at.strftime("%H:%M")} for n in notifs] # pyright: ignore[reportAttributeAccessIssue]
    
    # Optional: Mark as read immediately when fetched? 
    # Or keep them until user dismisses. For now, let's keep them unread.
    
    return JsonResponse({'notifications': data})

@csrf_exempt
def mark_notification_read_api(request):
    if request.method != "POST": return JsonResponse({}, status=405)
    notif_id = json.loads(request.body).get('id')
    CollegeNotification.objects.filter(id=notif_id).update(is_read=True)
    return JsonResponse({'message': 'Read'})

@csrf_exempt
def get_class_students_api(request):
    class_id = request.GET.get('class_id')
    try:
        academic_class = AcademicClass.objects.get(id=class_id)
        
        # Fetch all active students in this academic class
        # Note: Student no longer has course FK (refactored to M2M via Course.enrolled_students)
        students = Student.objects.filter(
            academic_class=academic_class,
            is_active=True
        ).values('id', 'name', 'reg_no', 'email') 
        
        return JsonResponse({
            'className': academic_class.class_name,
            'batch': academic_class.academic_year,
            'dept_id': academic_class.department.id, # Critical for Subject Dropdown # pyright: ignore[reportAttributeAccessIssue]
            'current_semester': academic_class.current_semester,
            'semester_start_date': str(academic_class.semester_start_date) if academic_class.semester_start_date else None,
            'semester_end_date': str(academic_class.semester_end_date) if academic_class.semester_end_date else None,
            'students': list(students)
        })
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

@csrf_exempt
def get_class_students_admin_all(request):
    """Return all students (active + inactive) for an academic class — Admin view."""
    class_id = request.GET.get('class_id')
    try:
        academic_class = AcademicClass.objects.get(id=class_id)
        students = Student.objects.filter(academic_class=academic_class).values('id', 'name', 'reg_no', 'email', 'is_active')
        return JsonResponse({
            'className': academic_class.class_name,
            'students': list(students)
        })
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@csrf_exempt
def add_student_to_existing_class_api(request):
    if request.method != "POST": return JsonResponse({}, status=405)
    data = json.loads(request.body)
    class_id = data.get('class_id')
    reg = data.get('reg_no').strip().upper()
    name = data.get('name')
    email = data.get('email', '')
    college_id = request.session.get('college_id')

    # 1. Check Duplicate in College
    if Student.objects.filter(academic_class__department__college_id=college_id, reg_no=reg).exists():
        return JsonResponse({'error': f'Register Number {reg} already exists in this college.'}, status=400)

    # 2. Create Student (joined_at defaults to today)
    new_student = Student.objects.create(
        academic_class_id=class_id,
        name=name,
        reg_no=reg,
        email=email
    )

    # 3. SYNC: Ensure faculty Course rosters for this academic class also contain this student
    # If a Course already has the student (matching reg_no), skip to avoid duplicates.
    try:
        ac_class = AcademicClass.objects.get(id=class_id)
        related_courses = Course.objects.filter(class_name=ac_class.class_name)
        for c in related_courses:
            if not c.enrolled_students.filter(reg_no=reg).exists():
                c.enrolled_students.add(new_student)
    except Exception:
        # If sync fails, don't block the primary operation
        logger.exception(f"Failed to sync student {reg} into course rosters for class_id={class_id}")
    return JsonResponse({'message': 'Student added successfully.'})

@csrf_exempt
@transaction.atomic
def delete_student_api(request):
    if request.method != "POST": return JsonResponse({'error': 'POST required'}, status=405)
    
    try:
        data = json.loads(request.body)
        student_id = data.get('student_id')
        
        # 1. Get Student
        target_student = Student.objects.get(id=student_id)
        
        # 2. Soft Delete (Mark Inactive) - Master List Architecture
        target_student.is_active = False
        target_student.save()
        
        # 3. FIX: Notify Faculty who have this student enrolled
        # Find active courses containing this student to notify the relevant teachers
        affected_courses = Course.objects.filter(enrolled_students=target_student, is_active=True).select_related('faculty')
        
        notified_ids = set()
        for course in affected_courses:
            if course.faculty and course.faculty.id not in notified_ids:
                try:
                    FacultyNotification.objects.create(
                        faculty=course.faculty,
                        message=f"STUDENT REMOVED - ADMIN UPDATE: Student {target_student.name} ({target_student.reg_no}) has been removed from the roster."
                    )
                    invalidate_faculty_dashboard_cache(course.faculty.id)
                    notified_ids.add(course.faculty.id)
                except Exception as notif_err:
                    logger.exception(f"Failed to notify faculty for student removal: {str(notif_err)}")

        return JsonResponse({'message': 'Student removed. Faculty rosters synced automatically.'})

    except Student.DoesNotExist:
        return JsonResponse({'error': 'Student not found'}, status=404)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)   


@csrf_exempt
def get_admin_student_profile(request, student_id):
    try:
        student = Student.objects.get(id=student_id)
        if not student.academic_class:
             return JsonResponse({'error': 'Student not assigned to an academic class'}, status=400)
             
        # 1. Fetch Courses (Enrolled Only)
        courses = Course.objects.filter(
            enrolled_students=student,
            is_active=True
        ).select_related('faculty')

        per_course = []
        overall_present_hours = 0
        overall_od_hours = 0
        overall_absent_hours = 0
        overall_total_hours = 0
        overall_total_sessions = 0

        for c in courses:
            # A. Get total hours for this course
            course_sessions = AttendanceSession.objects.filter(course=c)
            sessions_count = course_sessions.count()
            total_hours = course_sessions.aggregate(t=Sum('session_duration'))['t'] or 0
            
            # B. Get student's hours
            present_h = AttendanceRecord.objects.filter(student=student, session__course=c, status='Present').aggregate(h=Sum('session__session_duration'))['h'] or 0
            od_h = AttendanceRecord.objects.filter(student=student, session__course=c, status='OD').aggregate(h=Sum('session__session_duration'))['h'] or 0
            absent_h = AttendanceRecord.objects.filter(student=student, session__course=c, status='Absent').aggregate(h=Sum('session__session_duration'))['h'] or 0

            attended = present_h + od_h
            pct = round((attended / total_hours) * 100, 1) if total_hours > 0 else 0.0

            per_course.append({
                'course_id': c.id,
                'subject': c.subject_name,
                'code': c.subject_code,
                'percentage': pct,
                'present_hours': present_h,
                'od_hours': od_h,
                'absent_hours': absent_h,
                'total_hours': total_hours
            })

            # C. Aggregate Overall
            overall_present_hours += present_h
            overall_od_hours += od_h
            overall_absent_hours += absent_h
            overall_total_hours += total_hours
            overall_total_sessions += sessions_count

        # 2. Overall Calculations
        overall_attended = overall_present_hours + overall_od_hours
        overall_pct = round((overall_attended / overall_total_hours) * 100, 1) if overall_total_hours > 0 else 0.0

        # 3. Safe Skip Logic (The Fix)
        # We calculate the margin based on 75% of CURRENT total hours.
        required_hours = overall_total_hours * 0.75
        margin_hours = overall_attended - required_hours
        
        safe_skip_hours = 0
        status_label = "Critical"
        status_color = "red"
        calc_text = ""

        if margin_hours > 0:
            # Safe Case: Calculate how many future hours can be skipped
            # Formula: (Attended / 0.75) - Total
            # This projects how much total can grow before 75% is breached
            max_total_allowed = overall_attended / 0.75
            safe_skip_hours = int(max_total_allowed - overall_total_hours)
            
            status_label = "Safe Zone"
            status_color = "green"
            calc_text = f"Safe Margin: Approx {safe_skip_hours} hours can be skipped safely."
        else:
            # Critical Case
            shortage = abs(margin_hours)
            calc_text = f"Shortage: Need approx {int(shortage)} hours to reach 75%."

        return JsonResponse({
            'id': student.id,
            'name': student.name,
            'reg_no': student.reg_no,
            'email': student.email,
            'is_active': student.is_active,
            'per_course': per_course,
            'overall': {
                'present_hours': overall_present_hours, 
                'od_hours': overall_od_hours,
                'absent_hours': overall_absent_hours,
                'attended_hours': overall_attended,
                'total_hours': overall_total_hours,
                'total_sessions': overall_total_sessions,
                'percentage': overall_pct
            },
            'od_hours': overall_od_hours,
            'absent_hours': overall_absent_hours,
            'safe_skip': {
                'hours': safe_skip_hours,
                'status': status_label,
                'status_color': status_color,
                'message': calc_text
            }
        })
    except Student.DoesNotExist:
        return JsonResponse({'error': 'Student not found'}, status=404)
    except Exception as e:
        logger.exception(f"Profile Error: {str(e)}")
        return JsonResponse({'error': str(e)}, status=500)
