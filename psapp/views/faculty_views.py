from django.forms import ValidationError
from django.shortcuts import render, redirect
from django.http import HttpResponse, JsonResponse
from django.views.decorators.csrf import ensure_csrf_cookie, csrf_exempt
from django.views.decorators.cache import never_cache
from django.db import transaction
from django.db.models import Sum, Case, When, F, IntegerField
from django.core.mail import send_mail
from django.core.cache import cache
from psapp.models import NewFaculty, Course, Student, AttendanceSession, AttendanceRecord, CollegeNotification, ClassAssignmentRequest, FacultyJoinRequest, FacultyNotification, College
from .utils import invalidate_faculty_dashboard_cache
import json, logging

logger = logging.getLogger(__name__)

@ensure_csrf_cookie
@never_cache
def dashboard_template(request):
    faculty_id = request.session.get('faculty_id')
    if not faculty_id: return redirect('psapp:login')
    
    try:
        faculty = NewFaculty.objects.get(id=faculty_id)
        return render(request, "dashboard.html", {'faculty': faculty})
    except NewFaculty.DoesNotExist:
        return redirect('dashboard')

@csrf_exempt
def get_dashboard_data(request):
    # 1. Authentication Check
    faculty_id = request.session.get('faculty_id')
    jwt_user = getattr(request, 'jwt_user', None)
    if jwt_user and jwt_user['user_type'] == 'faculty':
        faculty_id = jwt_user['user_id']

    if not faculty_id: 
        return JsonResponse({'error': 'Unauthorized'}, status=401)

    # 2. Cache Check (5 Minutes)
    cache_key = f"faculty_dashboard:{faculty_id}"
    cached_data = cache.get(cache_key)
    if cached_data:
        return JsonResponse(cached_data)

    try:
        faculty = NewFaculty.objects.get(id=faculty_id)
        photo_url = faculty.profile_photo.url if faculty.profile_photo else ""
        faculty_reg_id = faculty.faculty_reg_id
    except NewFaculty.DoesNotExist:
        return JsonResponse({'error': 'Faculty not found'}, status=404)

    # 3. Optimized QuerySet
    # - Prefetch sessions and students to avoid N+1 queries
    # - Annotate total duration taught per course directly in the DB
    courses_qs = Course.objects.filter(faculty_id=faculty_id, is_active=True).prefetch_related(
        'enrolled_students',
        'sessions',
        'sessions__records',
        'sessions__records__student'
    ).select_related('faculty')

    classes_data = []
    
    # Global accumulators for cumulative analytics
    unique_student_regs_global = set()
    global_sessions_count = 0
    global_present_hours = 0
    global_possible_hours = 0

    for course in courses_qs:
        # --- A. PREPARE COURSE DATA ---
        sessions_qs = course.sessions.all().order_by('-date', '-start_session')
        students_qs = course.enrolled_students.filter(is_active=True).order_by('reg_no')
        
        # Track global students
        for s in students_qs:
            unique_student_regs_global.add(s.reg_no)

        student_list = [{'regNo': s.reg_no, 'name': s.name, 'id': s.id} for s in students_qs]
        
        # --- B. CALCULATE STATS (DB Aggregation) ---
        # Calculate total hours taught for this course
        total_hours_taken = sum(s.session_duration for s in sessions_qs)
        global_sessions_count += len(sessions_qs)

        # Calculate Attendance Percentage efficiently
        # We calculate (Total Student-Hours Attended) / (Total Student-Hours Possible)
        course_stats = AttendanceRecord.objects.filter(
            session__course=course,
            student__is_active=True
        ).aggregate(
            weighted_present=Sum(
                Case(
                    When(status__in=['Present', 'OD'], then=F('session__session_duration')),
                    default=0,
                    output_field=IntegerField()
                )
            )
        )

        weighted_present = course_stats['weighted_present'] or 0
        possible_hours = total_hours_taken * len(students_qs)
        
        attendance_avg = 0.0
        if possible_hours > 0:
            attendance_avg = round((weighted_present / possible_hours) * 100, 1)

        # Update global accumulators
        global_present_hours += weighted_present
        global_possible_hours += possible_hours

        # --- C. SERIALIZE SESSION RECORDS (For Timeline) ---
        attendance_records = []
        for session in sessions_qs:
            # In-memory counting is faster here because 'records' are prefetched
            recs = list(session.records.all()) 
            
            p_count = sum(1 for r in recs if r.status == 'Present')
            od_count = sum(1 for r in recs if r.status == 'OD')
            a_count = sum(1 for r in recs if r.status == 'Absent')
            
            session_student_details = [{
                'regNo': r.student.reg_no,
                'name': r.student.name,
                'status': r.status
            } for r in recs]

            attendance_records.append({
                'id': session.id,
                'date': session.date.strftime("%Y-%m-%d"),
                'sessionDisplay': f"{session.start_session}-{session.end_session}",
                'duration': session.session_duration,
                'total': len(recs),
                'presentCount': p_count,
                'odCount': od_count,
                'absentCount': a_count,
                'records': session_student_details
            })

        # --- D. BUILD CLASS OBJECT ---
        classes_data.append({
            'id': course.id,
            'type': 'Personal' if course.is_personal else 'Official',
            'className': course.class_name,
            'subjectName': course.subject_name,
            'subjectCode': course.subject_code,
            'isAssigned': course.is_assigned,
            'totalHoursTaken': total_hours_taken,
            'totalHours': course.total_hours,
            'attendance_avg': attendance_avg,
            'student_count': len(student_list),
            'createdAt': course.created_at.strftime("%d %b %Y"),
            'students': student_list,
            'attendanceRecords': attendance_records
        })

    # 4. Final Cumulative Calculation
    overall_attendance_pct = 0.0
    if global_possible_hours > 0:
        overall_attendance_pct = round((global_present_hours / global_possible_hours) * 100, 1)

    cumulative_analytics = {
        'total_courses': len(classes_data),
        'total_students': len(unique_student_regs_global),
        'total_sessions': global_sessions_count,
        'overall_attendance_percentage': overall_attendance_pct,
        'total_present_hours': global_present_hours,
        'total_possible_hours': global_possible_hours
    }

    response_data = {
        'classes': classes_data,
        'cumulative_analytics': cumulative_analytics,
        'faculty_photo': photo_url,
        'faculty_id': faculty_reg_id
    }

    # 5. Set Cache and Return
    cache.set(cache_key, response_data, 300) # 5 minutes
    return JsonResponse(response_data)

@transaction.atomic
@csrf_exempt
def create_class_api(request):
    if request.method != "POST": 
        return JsonResponse({'error': 'POST required'}, status=405)
    
    try:
        data = json.loads(request.body)
        faculty_id = request.session.get('faculty_id')
        
        # Security Check
        if not faculty_id:
            return JsonResponse({'error': 'Unauthorized'}, status=401)

        faculty = NewFaculty.objects.get(id=faculty_id)
        
        # 1. Create the Personal Course
        # This course is marked is_personal=True so it doesn't show up in College Reports
        total_hours = data.get('totalHours', 45)
        try:
            total_hours = int(total_hours)
            if total_hours <= 0 or total_hours > 500:
                raise ValueError
        except (TypeError, ValueError):
            return JsonResponse({'error': 'Invalid total hours. Must be a positive integer up to 500.'}, status=400)

        # Process and validate duplicate student registration numbers
        student_list = data.get('students', [])
        seen_regs = set()
        for s in student_list:
            reg_input = s.get('regNo', '').strip().upper()
            if not reg_input:
                return JsonResponse({'error': 'Registration number is required for all students.'}, status=400)
            if reg_input in seen_regs:
                return JsonResponse({'error': f'Duplicate student registration number detected: {reg_input}'}, status=400)
            seen_regs.add(reg_input)

        new_course = Course.objects.create(
            faculty=faculty,
            class_name=data.get('className'),
            subject_name=data.get('subjectName'),
            subject_code=data.get('subjectCode'),
            total_hours=total_hours,
            is_assigned=False, 
            is_personal=True,  
            is_active=True
        )

        # 2. Process Students (The "Skip Validation" Logic)
        student_list = data.get('students', [])
        students_to_add = []

        for s in student_list:
            reg_input = s['regNo'].strip().upper()
            
            # LOGIC FIX: 
            # We strictly search for a student that belongs to THIS Faculty (created_by_faculty)
            # AND has NO College link (college=None).
            # This ignores the Official College List completely.
            personal_student, created = Student.objects.get_or_create(
                reg_no=reg_input,
                created_by_faculty=faculty, # Private to this faculty
                college=None,               # STRICTLY NOT linked to college
                defaults={
                    'name': s['name'],
                    'email': s.get('email', ''),
                    'student_type': 'Personal',
                    'academic_class': None # No link to B.Tech/BE master structure
                }
            )
            
            # If the faculty wants to rename THEIR personal student, allow it.
            # (e.g., changing "John" to "John Doe")
            if not created and personal_student.name != s['name']:
                personal_student.name = s['name']
                personal_student.save()

            students_to_add.append(personal_student)

        # 3. Link students to the new course
        new_course.enrolled_students.set(students_to_add)

        # 4. Notify Admin (Optional - just for logs)
        if faculty.department_link and faculty.department_link.college:
            CollegeNotification.objects.create(
                college=faculty.department_link.college,
                message=f"Faculty {faculty.name} created a Personal Class: '{new_course.subject_name}' with {len(students_to_add)} private students."
            )
        
        # Invalidate cache so the new class appears on Dashboard immediately
        invalidate_faculty_dashboard_cache(faculty_id) 

        return JsonResponse({
            'message': 'Personal class created successfully.', 
            'id': new_course.id
        })

    except Exception as e:
        import traceback
        print(traceback.format_exc())
        return JsonResponse({'error': str(e)}, status=500)

@transaction.atomic
@csrf_exempt
def save_attendance_api(request):
    if request.method != "POST": 
        return JsonResponse({'error': 'POST method required'}, status=405)

    try:
        data = json.loads(request.body)
        course_id = data.get('classId')
        date_str = data.get('date')
        records_data = data.get('records', [])
        
        # 1. Validation
        try:
            start_sess = int(data.get('startSession'))
            end_sess = int(data.get('endSession'))
            if start_sess <= 0 or end_sess <= 0 or start_sess > end_sess:
                raise ValueError
        except (TypeError, ValueError):
            return JsonResponse({'error': 'Invalid session periods. Must be positive non-zero numbers and start session must not exceed end session.'}, status=400)

        # 2. Query the Course row WITHOUT locking (Concurrency Fix)
        course = Course.objects.get(id=course_id)
        
        submitted_regs = [r.get('regNo') for r in records_data]
        conflicts = AttendanceRecord.objects.filter(
            student__reg_no__in=submitted_regs,
            session__date=date_str,
            session__start_session__lte=end_sess,
            session__end_session__gte=start_sess
        ).exclude(
            session__course_id=course_id 
        ).select_related('student', 'session__course')

        if conflicts.exists():
            # C. If conflict found, stop everything and return error
            c = conflicts.first()
            
            conflict_name = c.student.name
            conflict_reg = c.student.reg_no
            conflict_subject = c.session.course.subject_name
            conflict_period = f"{c.session.start_session}-{c.session.end_session}"
            
            error_msg = (
                f"Conflict detected! Student {conflict_name} ({conflict_reg}) "
                f"is already marked present in '{conflict_subject}' "
                f"during Period {conflict_period}."
            )
            return JsonResponse({'error': error_msg}, status=400)

        # 3. Create Session (The model's clean() method will auto-check overlaps)
        try:
            session = AttendanceSession.objects.create(
                course=course,
                date=date_str,
                start_session=start_sess,
                end_session=end_sess,
                session_duration=(end_sess - start_sess + 1)
            )
        except ValidationError as e:
            return JsonResponse({'error': str(e.message)}, status=400)

        # 4. Bulk Prepare Records (Optimization)
        records_data = data.get('records', [])
        
        # Fetch all students in this course to map RegNo -> ID (1 DB Query)
        enrolled_students = {s.reg_no: s.id for s in course.enrolled_students.all()}
        
        records_to_create = []
        p_count = 0
        a_count = 0

        for r in records_data:
            reg_no = r.get('regNo')
            status = r.get('status')
            
            if reg_no in enrolled_students:
                records_to_create.append(AttendanceRecord(
                    session=session,
                    student_id=enrolled_students[reg_no],
                    status=status
                ))
                if status == 'Present': p_count += 1
                elif status == 'Absent': a_count += 1

        # 5. Bulk Insert (1 DB Query instead of 60)
        AttendanceRecord.objects.bulk_create(records_to_create)

        # 6. Update Session Counts
        session.total_present = p_count
        session.total_absent = a_count
        session.save()

        # 7. Invalidate Cache
        invalidate_faculty_dashboard_cache(request.session.get('faculty_id'))

        return JsonResponse({'message': 'Attendance saved successfully'})

    except Course.DoesNotExist:
        return JsonResponse({'error': 'Course not found'}, status=404)
    except Exception as e:
        logger.exception("Save Attendance Error")
        return JsonResponse({'error': str(e)}, status=500)

@csrf_exempt
@transaction.atomic
def edit_student_api(request):
    if request.method != "POST": 
        return JsonResponse({'error': 'POST required'}, status=405)
    
    try:
        data = json.loads(request.body)
        student_id = data.get('student_id')
        
        if not student_id:
            return JsonResponse({'error': 'student_id is required'}, status=400)
        
        # 1. Get Student Record
        target_student = Student.objects.get(id=student_id)
        old_val = f"{target_student.name} ({target_student.reg_no})"

        # 2. Update Student Data
        target_student.name = data.get('name', target_student.name).strip()
        
        # Handle reg_no with fallback - supports both camelCase and snake_case from frontend
        new_reg = (data.get('regNo') or data.get('reg_no') or target_student.reg_no).strip().upper()
        target_student.reg_no = new_reg
        
        target_student.email = data.get('email', target_student.email)
        target_student.save()

        # 3. Notification Logic - Only if faculty_id exists (not for admin)
        # Wrapped in try/except to prevent crashes
        try:
            faculty_id = request.session.get('faculty_id') if hasattr(request, 'session') else None
            
            if faculty_id is not None:
                try:
                    # Get Faculty details for notification message
                    faculty = NewFaculty.objects.get(id=faculty_id)
                    
                    # Ensure college_id is available
                    college_id = request.session.get('college_id') if hasattr(request, 'session') else None
                    if not college_id:
                        college_id = target_student.college_id
                    
                    # Get College object
                    college = College.objects.get(id=college_id)
                    
                    # Create notification with all required fields
                    CollegeNotification.objects.create(
                        college=college,
                        message=f"DATA UPDATE: Faculty {faculty.name} edited student {old_val} -> {target_student.name} ({target_student.reg_no}).",
                        is_read=False
                    )
                except NewFaculty.DoesNotExist:
                    logger.warning(f"Faculty {faculty_id} not found for notification")
                except College.DoesNotExist:
                    logger.warning(f"College {college_id} not found for notification")
                except Exception as notification_error:
                    logger.error(f"Notification Error (non-critical): {notification_error}")
        except Exception as session_error:
            logger.error(f"Session access error (non-critical): {session_error}")

        return JsonResponse({
            'message': 'Student updated successfully.',
            'student': {
                'id': target_student.id,
                'name': target_student.name,
                'reg_no': target_student.reg_no,
                'email': target_student.email
            }
        })

    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON data'}, status=400)
    except Student.DoesNotExist:
        return JsonResponse({'error': 'Student not found'}, status=404)
    except Exception as e:
        logger.error(f"Error in edit_student_api: {str(e)}")
        return JsonResponse({'error': f'Failed to update student: {str(e)}'}, status=500)

def delete_class_api(request, course_id):
    if request.method != "DELETE": 
        return JsonResponse({'error': 'DELETE required'}, status=405)
    
    faculty_id = request.session.get('faculty_id')
    
    try:
        # 1. Get the Course
        course = Course.objects.get(id=course_id, faculty_id=faculty_id)
        
        # 2. Check if this was assigned by an Admin
        linked_requests = ClassAssignmentRequest.objects.filter(
            faculty_id=faculty_id,
            subject__course_code=course.subject_code,
            academic_class__class_name=course.class_name,
            status='Approved'
        )
        
        message = ""

        if linked_requests.exists():
            for req in linked_requests:
                req.status = 'Terminated'
                req.save()
                
                # --- FIX: Handle Orphaned Faculty Name ---
                fac_name = "Unknown Faculty"
                if course.faculty:
                    fac_name = course.faculty.name
                
                # Notify Admin
                CollegeNotification.objects.create(
                    college=req.college,
                    message=f"ALERT: Faculty {fac_name} has DELETED the assigned class '{course.subject_name}' ({course.class_name})."
                )
            message = "Class deleted. Department Admin has been notified."
        else:
            message = "Class deleted permanently. This action cannot be undone."

        # 3. Delete the Course Data
        course.delete()
        invalidate_faculty_dashboard_cache(faculty_id)
        return JsonResponse({'message': message})

    except Course.DoesNotExist:
        return JsonResponse({'error': 'Class not found'}, status=404)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

def edit_profile_api(request):
    if request.method != "POST": return JsonResponse({'error': 'POST required'}, status=405)
    faculty_id = request.session.get('faculty_id')
    
    try:
        faculty = NewFaculty.objects.get(id=faculty_id)
        faculty.name = request.POST.get('name', faculty.name)
        faculty.college_name = request.POST.get('college_name', faculty.college_name)
        faculty.designation = request.POST.get('designation', faculty.designation)
        faculty.department = request.POST.get('department', faculty.department)
        faculty.mobile_num = request.POST.get('mobile', faculty.mobile_num)
        
        if 'profile_photo' in request.FILES:
            faculty.profile_photo = request.FILES['profile_photo']
            
        faculty.save()
        return JsonResponse({'message': 'Profile updated', 'photo_url': faculty.profile_photo.url if faculty.profile_photo else None})
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

@transaction.atomic
@csrf_exempt
def copy_class_api(request):
    if request.method != "POST": 
        return JsonResponse({'error': 'POST required'}, status=405)
    
    faculty_id = request.session.get('faculty_id')
    
    try:
        data = json.loads(request.body)
        source_id = data.get('source_class_id')
        
        # 1. Fetch Source Course
        # (Can be an Admin Assigned course OR another Personal course)
        source_course = Course.objects.get(id=source_id, faculty_id=faculty_id)
        faculty = NewFaculty.objects.get(id=faculty_id)

        # 2. Create New Personal Course (Decoupled)
        new_course = Course.objects.create(
            faculty=faculty,
            class_name=data.get('className') or source_course.class_name,
            subject_name=data.get('subjectName') or source_course.subject_name,
            subject_code=data.get('subjectCode') or source_course.subject_code,
            total_hours=data.get('totalHours') or source_course.total_hours,
            is_assigned=False, # It is now Personal
            is_personal=True,  # Explicitly Personal
            is_active=True,
            parent_course_id=source_course.id # Traceability
        )

        # 3. DEEP COPY STUDENTS (The "Hybrid" Logic)
        # We fetch students from the source, but we create NEW Personal copies 
        # so modifying them in the new class doesn't affect the Admin Roster.
        
        source_students = source_course.enrolled_students.all()
        new_personal_students = []

        for src_stu in source_students:
            # Create a detached copy
            personal_copy = Student.objects.create(
                name=src_stu.name,
                reg_no=src_stu.reg_no,
                email=src_stu.email,
                student_type='Personal',       # Mark as Personal
                created_by_faculty=faculty,    # Owned by Faculty
                college=None,                  # Detached from College
                academic_class=None            # Detached from Master Roster
            )
            new_personal_students.append(personal_copy)

        # 4. Link new personal students to the new course
        new_course.enrolled_students.set(new_personal_students)

        # 5. Notify Admin about the duplication
        if faculty.department_link and faculty.department_link.college:
            CollegeNotification.objects.create(
                college=faculty.department_link.college,
                message=f"INFO: Faculty {faculty.name} duplicated '{source_course.subject_name}' into a Personal Class."
            )
        invalidate_faculty_dashboard_cache(faculty_id)

        return JsonResponse({
            'message': 'Class duplicated as Personal. Student data cloned successfully.',
            'new_id': new_course.id
        })

    except Course.DoesNotExist:
        return JsonResponse({'error': 'Source class not found'}, status=404)
    except Exception as e:
        logger.exception("Copy Class Error")
        return JsonResponse({'error': str(e)}, status=500)
    
    
def get_student_stats_api(request, student_id):
    try:
        # FIX: Use select_related to reduce DB queries (N+1 optimization)
        # Student no longer has 'course' field; use academic_class instead
        student = Student.objects.select_related('academic_class', 'college').get(id=student_id)
        
        # FIX: Single aggregation query instead of 3 separate ones
        record_stats = AttendanceRecord.objects.filter(student=student).values('status').annotate(
            total_duration=Sum('session__session_duration')
        ).order_by('status')
        
        record_dict = {r['status']: r['total_duration'] for r in record_stats}
        present = record_dict.get('Present', 0)
        od = record_dict.get('OD', 0)
        absent = record_dict.get('Absent', 0)

        # FIX: Build per-course breakdown with prefetch_related to avoid N+1 queries
        per_course = []
        overall_present = 0
        overall_total = 0
        # Get courses where this student is enrolled (M2M relationship)
        courses = Course.objects.filter(enrolled_students=student, 
                                       is_active=True
                                       ).prefetch_related('sessions')

        # Batch fetch all attendance records at once instead of per-course queries
        if courses:
            course_ids = [c.id for c in courses]
            # Single query for all records with filtering
            all_records_by_course = {}
            for record in AttendanceRecord.objects.filter(student=student, session__course_id__in=course_ids).select_related('session'):
                course_id = record.session.course_id
                if course_id not in all_records_by_course:
                    all_records_by_course[course_id] = {'Present': 0, 'OD': 0, 'Absent': 0}
                all_records_by_course[course_id][record.status] = all_records_by_course[course_id].get(record.status, 0) + record.session.session_duration
        else:
            all_records_by_course = {}

        for c in courses:
            # FIX: Use cached session data instead of new queries
            total_hours = sum(s.session_duration for s in c.sessions.all())
            
            # FIX: Use pre-fetched record stats instead of new queries
            record_stats_c = all_records_by_course.get(c.id, {'Present': 0, 'OD': 0, 'Absent': 0})
            present_hours = record_stats_c['Present']
            od_hours_c = record_stats_c['OD']
            absent_hours_c = record_stats_c['Absent']

            attended = present_hours + od_hours_c
            pct = round((attended / total_hours) * 100, 1) if total_hours > 0 else 0.0
            per_course.append({
                'course_id': c.id,
                'subject': c.subject_name,
                'code': c.subject_code,
                'percentage': pct,
                'present_hours': present_hours,
                'od_hours': od_hours_c,
                'absent_hours': absent_hours_c,
                'total_hours': total_hours
            })

            overall_present += attended
            overall_total += total_hours

        total_taught = overall_total
        eff_present = present + od
        pct = round((eff_present / total_taught) * 100, 1) if total_taught > 0 else 0

        status_label = "Safe Zone" if pct >= 75 else "Critical"
        status_color = "green" if pct >= 75 else "red"

        return JsonResponse({
            'name': student.name, 'regNo': student.reg_no, 'email': student.email,
            'course': student.academic_class.class_name if student.academic_class else '',
            'subject': 'Multiple Courses' if overall_total > 0 else '',
            'total': total_taught, 'present': present, 'od': od, 'absent': absent,
            'percentage': pct, 'statusLabel': status_label, 'statusColor': status_color,
            'per_course': per_course,
            'overall': {'present_hours': overall_present, 'total_hours': overall_total, 'percentage': round((overall_present / overall_total) * 100, 1) if overall_total > 0 else 0}
        })
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

def get_defaulters_list(request, course_id):
    try:
        course = Course.objects.get(id=course_id)
        total_course_hours = AttendanceSession.objects.filter(course=course).aggregate(t=Sum('session_duration'))['t'] or 0
        # FIX: Using M2M enrolled_students instead of old course.students
        students = course.enrolled_students.filter(is_active=True)
        defaulters = []

        for student in students:
            attended = AttendanceRecord.objects.filter(student=student, status__in=['Present', 'OD']).aggregate(h=Sum('session__session_duration'))['h'] or 0
            pct = round((attended / total_course_hours) * 100, 1) if total_course_hours > 0 else 0
            if pct < 75:
                defaulters.append({'name': student.name, 'regNo': student.reg_no, 'email': student.email, 'total': total_course_hours, 'present': attended, 'percentage': pct, 'severity': 'Critical'})
        
        defaulters.sort(key=lambda x: x['percentage'])
        return JsonResponse({'className': course.class_name, 'subjectName': course.subject_name, 'defaulters': defaulters})
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

def get_leaderboard_api(request, course_id):
    try:
        course = Course.objects.get(id=course_id)
        students = course.enrolled_students.filter(is_active=True)
        data = []
        
        # For each student, calculate percentage based on their personal total possible hours
        for s in students:
            # Get all sessions where this student could have been marked
            student_sessions = AttendanceRecord.objects.filter(student=s, session__course=course).values('session_id').distinct()
            total_possible_hours = AttendanceSession.objects.filter(course=course, id__in=student_sessions).aggregate(t=Sum('session_duration'))['t'] or 0
            
            # Get attended hours (Present + OD)
            attended = AttendanceRecord.objects.filter(student=s, session__course=course, status__in=['Present', 'OD']).aggregate(h=Sum('session__session_duration'))['h'] or 0
            
            pct = round((attended / total_possible_hours) * 100, 1) if total_possible_hours > 0 else 0
            data.append({'name': s.name, 'regNo': s.reg_no, 'percentage': pct})
        
        data.sort(key=lambda x: x['percentage'], reverse=True)
        return JsonResponse({'leaderboard': data})
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)
    
@csrf_exempt
def send_warning_emails_api(request):
    if request.method != "POST": return JsonResponse({'error': 'POST required'}, status=405)
    try:
        data = json.loads(request.body)
        faculty_id = request.session.get('faculty_id')
        faculty = NewFaculty.objects.get(id=faculty_id)
        
        import threading
        count = 0
        students_to_email = [d for d in data.get('students', []) if d.get('email')]
        
        def send_warning_emails_bg():
            for d in students_to_email:
                try:
                    send_mail(
                        f"Warning: {d['subject']}",
                        f"Dear {d['name']}, your attendance is {d['percentage']}%. Please attend classes.\nRegards, {faculty.name}",
                        "askabhitechnology@gmail.com",
                        [d['email']],
                        fail_silently=True
                    )
                except Exception as e:
                    logger.error(f"Failed to send warning email to {d['email']}: {str(e)}")

        threading.Thread(target=send_warning_emails_bg).start()
        count = len(students_to_email)
        return JsonResponse({'message': f'Sent {count} emails'})
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

@transaction.atomic
@csrf_exempt
def update_attendance_api(request):
    if request.method != "POST": return JsonResponse({'error': 'POST required'}, status=405)
    try:
        data = json.loads(request.body)
        session = AttendanceSession.objects.get(id=data.get('sessionId'))
        records = data.get('records')

        p_count = 0; a_count = 0
        for r in records:
            status = r['status']
            if status == 'Present': p_count += 1
            elif status == 'Absent': a_count += 1
            AttendanceRecord.objects.filter(session=session, student__reg_no=r['regNo']).update(status=status)

        session.total_present = p_count; session.total_absent = a_count
        session.save()

        # Clear faculty dashboard cache
        invalidate_faculty_dashboard_cache(request.session.get('faculty_id'))

        return JsonResponse({'message': 'Attendance updated'})

    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON data provided'}, status=400)
    except AttendanceSession.DoesNotExist:
        return JsonResponse({'error': 'Attendance session not found'}, status=404)
    except Exception as e:
        logger.exception(f"Unexpected error updating attendance: {str(e)}")
        return JsonResponse({'error': 'An unexpected error occurred while updating attendance'}, status=500)

@csrf_exempt
def respond_faculty_request_api(request):
    if request.method != "POST": return JsonResponse({'error': 'POST required'}, status=405)
    
    faculty_id = request.session.get('faculty_id')
    try:
        data = json.loads(request.body)
        req_id = data.get('request_id')
        req_type = data.get('type') 
        action = data.get('action') 
        
        with transaction.atomic():
            # --- 1. HANDLE JOIN REQUEST (College Join) ---
            if req_type == 'join':
                join_req = FacultyJoinRequest.objects.select_for_update().get(id=req_id, faculty_id=faculty_id)
                
                if join_req.status != 'Pending':
                    return JsonResponse({'message': 'Request already processed.'})

                if action == 'Accept':
                    join_req.status = 'Approved'
                    join_req.save()
                    
                    faculty = NewFaculty.objects.get(id=faculty_id)
                    faculty.college_name = join_req.college.college_name
                    faculty.department_link_id = join_req.department.id 
                    faculty.department = join_req.department.name
                    faculty.save()
                    
                    invalidate_college_dashboard_cache(join_req.college.id)
                    invalidate_faculty_dashboard_cache(faculty_id)
                    
                    CollegeNotification.objects.create(college=join_req.college, message=f"{faculty.name} joined {faculty.department}.")
                    return JsonResponse({'message': 'Welcome to the college!'})
                else:
                    join_req.status = 'Rejected'
                    join_req.save()
                    return JsonResponse({'message': 'Request rejected.'})

            # --- 2. HANDLE CLASS ASSIGNMENT (Core & Elective/Lab) ---
            elif req_type == 'class':
                class_req = ClassAssignmentRequest.objects.select_for_update().get(id=req_id, faculty_id=faculty_id)
                
                if class_req.status != 'Pending':
                    return JsonResponse({'message': 'Request already processed.'})

                if action == 'Accept':
                    # A. Check if this is a Special Course (Elective/Lab with specific students)
                    if class_req.student_list_json:
                        # 1. Parse Data
                        student_ids = json.loads(class_req.student_list_json)
                        batch_name = class_req.batch_name or "Main"
                        
                        # 2. Create the Course (Now it happens on Accept)
                        new_course = Course.objects.create(
                            academic_class=class_req.academic_class,
                            faculty_id=faculty_id,
                            class_name=class_req.academic_class.class_name,
                            subject_name=class_req.subject.course_name,
                            subject_code=class_req.subject.course_code,
                            course_type=class_req.subject.course_type,
                            batch_name=batch_name,
                            total_hours=class_req.total_hours,
                            is_assigned=True,
                            is_active=True,
                            semester=class_req.subject.semester or 0
                        )
                        
                        # 3. Link Specific Students
                        selected_students = Student.objects.filter(id__in=student_ids)
                        new_course.enrolled_students.set(selected_students)
                        
                        msg = f"Accepted! {new_course.subject_name} ({batch_name}) added to dashboard."

                    else:
                        # B. Standard Core Course Logic (Entire Class)
                        
                        # Check for Reassignment (Orphaned Course)
                        orphaned_course = Course.objects.filter(
                            class_name=class_req.academic_class.class_name,
                            subject_code=class_req.subject.course_code,
                            faculty__isnull=True,
                            batch_name='Main' # Assuming core courses are Main
                        ).first()

                        if orphaned_course:
                            # Adopt existing course
                            orphaned_course.faculty_id = faculty_id
                            orphaned_course.is_assigned = True
                            orphaned_course.is_active = True
                            orphaned_course.save()
                            msg = "Class reassigned! History preserved."
                        else:
                            # Create NEW Core Course
                            if Course.objects.filter(
                                faculty_id=faculty_id, 
                                subject_code=class_req.subject.course_code,
                                class_name=class_req.academic_class.class_name,
                                is_active=True
                            ).exists():
                                class_req.status = 'Approved'
                                class_req.save()
                                return JsonResponse({'message': 'You already have this class.'})

                            new_course = Course.objects.create(
                                academic_class=class_req.academic_class,
                                faculty_id=faculty_id,
                                class_name=class_req.academic_class.class_name,
                                subject_name=class_req.subject.course_name,
                                subject_code=class_req.subject.course_code,
                                course_type=class_req.subject.course_type,
                                batch_name="Main",
                                total_hours=class_req.total_hours,
                                is_assigned=True,
                                is_active=True
                            )

                            # Link ALL students from the master class
                            master_students = Student.objects.filter(
                                academic_class=class_req.academic_class, 
                                is_active=True
                            )
                            new_course.enrolled_students.set(master_students)
                            msg = "New class created. Master student roster linked."

                    # Finalize Request
                    class_req.status = 'Approved'
                    class_req.save()
                    
                    invalidate_faculty_dashboard_cache(faculty_id)

                    CollegeNotification.objects.create(
                        college=class_req.college, 
                        message=f"{NewFaculty.objects.get(id=faculty_id).name} accepted: {class_req.subject.course_name}."
                    )
                    return JsonResponse({'message': msg})
                else:
                    class_req.status = 'Rejected'
                    class_req.save()
                    return JsonResponse({'message': 'Rejected.'})

    except Exception as e:
        import traceback
        print(traceback.format_exc())
        return JsonResponse({'error': str(e)}, status=500)    

def get_faculty_notifications_api(request):
    faculty_id = request.session.get('faculty_id')
    if not faculty_id: return JsonResponse({'notifications': []})
    
    # Get invites (requests) AND system notifications
    notifs = FacultyNotification.objects.filter(faculty_id=faculty_id, is_read=False).order_by('-created_at')
    
    data = [{'id': n.id, 'message': n.message, 'date': n.created_at.strftime("%d %b")} for n in notifs] # pyright: ignore[reportAttributeAccessIssue]
    return JsonResponse({'notifications': data})

@csrf_exempt
def mark_faculty_notif_read(request):
    if request.method != "POST": return JsonResponse({}, status=405)
    notif_id = json.loads(request.body).get('id')
    FacultyNotification.objects.filter(id=notif_id).update(is_read=True)
    return JsonResponse({'message': 'Read'})


def get_faculty_requests_api(request):
    faculty_id = request.session.get('faculty_id')
    if not faculty_id: return JsonResponse({'error': 'Unauthorized'}, status=401)
    
    # 1. Get Join Requests
    join_reqs = FacultyJoinRequest.objects.filter(faculty_id=faculty_id, status='Pending')
    
    # 2. Get Class Requests
    class_reqs = ClassAssignmentRequest.objects.filter(faculty_id=faculty_id, status='Pending')
    
    data = []
    
    for req in join_reqs:
        data.append({
            'type': 'join',
            'request_id': req.id, # pyright: ignore[reportAttributeAccessIssue]
            'title': "Join College Request",
            'subtitle': f"{req.college.college_name} wants you to join {req.department.name}.",
            'meta': "Department Transfer"
        })

    for req in class_reqs:
        # Check if this is a Reassignment (Orphaned Course exists)
        is_reassign = Course.objects.filter(
            class_name=req.academic_class.class_name,
            subject_code=req.subject.course_code,
            faculty__isnull=True
        ).exists()

        meta_text = f"{req.total_hours} Hours • {req.subject.course_code}"
        if is_reassign:
            meta_text = "🔄 REASSIGNED COURSE • " + meta_text

        data.append({
            'type': 'class',
            'request_id': req.id, # pyright: ignore[reportAttributeAccessIssue]
            'title': "Subject Assignment",
            'subtitle': f"Take '{req.subject.course_name}' for {req.academic_class.class_name}?",
            'meta': meta_text # Faculty will see the icon here
        })
        
    return JsonResponse({'requests': data})
