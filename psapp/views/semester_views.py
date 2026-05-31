from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.db import transaction
from django.core.mail import send_mail
from psapp.models import College, Department, AcademicClass, Student, NewFaculty, FacultyNotification, Course, FacultyJoinRequest, ClassAssignmentRequest
from .utils import invalidate_college_dashboard_cache, invalidate_faculty_dashboard_cache
import json, random, time, math, logging, secrets, hmac, threading

logger = logging.getLogger(__name__)

def send_delete_otp_api(request):
    if request.method != "POST": return JsonResponse({}, status=405)
    college_id = request.session.get('college_id')
    if not college_id: return JsonResponse({'error': 'Unauthorized'}, status=401)
    
    try:
        college = College.objects.get(id=college_id)
        otp = str(secrets.randbelow(900000) + 100000)
        request.session['delete_otp'] = otp
        request.session['delete_verified'] = False
        
        def send_delete_email_bg():
            try:
                send_mail(
                    "Confirm Deletion - Present Sir",
                    f"Your OTP to authorize deletion is: {otp}\n\nThis action cannot be undone.",
                    "presentsirtechnologies@gmail.com",
                    [college.admin_email],
                    fail_silently=False
                )
            except Exception as e:
                logger.error(f"Failed to send delete OTP email: {str(e)}")

        threading.Thread(target=send_delete_email_bg).start()
        return JsonResponse({'message': 'OTP sent to admin email.'})
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

def verify_delete_otp_api(request):
    if request.method != "POST": return JsonResponse({}, status=405)
    otp = json.loads(request.body).get('otp')
    server_otp = request.session.get('delete_otp')
    
    if otp and server_otp and hmac.compare_digest(str(otp), str(server_otp)):
        request.session['delete_verified'] = True
        return JsonResponse({'message': 'Verified'})
    return JsonResponse({'error': 'Invalid OTP'}, status=400)

@csrf_exempt
@transaction.atomic
def delete_department_api(request):
    if request.method != "POST": return JsonResponse({}, status=405)
    if not request.session.get('delete_verified'): return JsonResponse({'error': 'OTP not verified'}, status=403)

    try:
        dept_id = json.loads(request.body).get('dept_id')
        Department.objects.get(id=dept_id).delete()

        # Clear college dashboard cache
        invalidate_college_dashboard_cache(request.session.get('college_id'))

        request.session['delete_verified'] = False # Reset
        return JsonResponse({'message': 'Department Deleted'})
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON data provided'}, status=400)
    except Department.DoesNotExist:
        return JsonResponse({'error': 'Department not found'}, status=404)
    except Exception as e:
        logger.exception(f"Unexpected error deleting department: {str(e)}")
        return JsonResponse({'error': 'An unexpected error occurred while deleting the department'}, status=500)

@csrf_exempt
@transaction.atomic
def delete_class_admin_api(request):
    if request.method != "POST": return JsonResponse({}, status=405)
    if not request.session.get('delete_verified'): return JsonResponse({'error': 'OTP not verified'}, status=403)

    try:
        class_id = json.loads(request.body).get('class_id')
        AcademicClass.objects.get(id=class_id).delete()

        # Clear college dashboard cache
        invalidate_college_dashboard_cache(request.session.get('college_id'))

        request.session['delete_verified'] = False # Reset
        return JsonResponse({'message': 'Class Deleted'})
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON data provided'}, status=400)
    except AcademicClass.DoesNotExist:
        return JsonResponse({'error': 'Class not found'}, status=404)
    except Exception as e:
        logger.exception(f"Unexpected error deleting class: {str(e)}")
        return JsonResponse({'error': 'An unexpected error occurred while deleting the class'}, status=500)


def send_action_otp_api(request):
    """
    Universal OTP Sender for: 
    1. delete_student
    2. terminate_faculty
    3. delete_class
    """
    if request.method != "POST": return JsonResponse({}, status=405)
    
    college_id = request.session.get('college_id')
    if not college_id: return JsonResponse({'error': 'Unauthorized'}, status=401)
    
    data = json.loads(request.body)
    action_type = data.get('action_type') # 'student', 'faculty', 'class'
    target_id = data.get('target_id')
    extra_data = data.get('extra_data', {}) # For replacement_id in faculty termination

    try:
        college = College.objects.get(id=college_id)
        otp = str(secrets.randbelow(900000) + 100000)
        
        # Save Context to Session
        request.session['otp_context'] = {
            'otp': otp,
            'action': action_type,
            'target_id': target_id,
            'extra': extra_data,
            'verified': False
        }
        
        def send_action_email_bg():
            try:
                send_mail(
                    f"Action Authorization - {action_type.upper()}",
                    f"Your OTP to authorize {action_type} deletion/termination is: {otp}",
                    "presentsirtechnologies@gmail.com",
                    [college.admin_email],
                    fail_silently=False
                )
            except Exception as e:
                logger.error(f"Failed to send action OTP email: {str(e)}")

        threading.Thread(target=send_action_email_bg).start()
        return JsonResponse({'message': 'OTP sent to Admin Email'})
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

@csrf_exempt
def verify_action_and_execute_api(request):
    """Verifies OTP and executes the stored action immediately"""
    if request.method != "POST": return JsonResponse({}, status=405)
    
    user_otp = json.loads(request.body).get('otp')
    context = request.session.get('otp_context')
    
    if not context or not user_otp or not hmac.compare_digest(str(user_otp), str(context.get('otp'))):
        return JsonResponse({'error': 'Invalid or Expired OTP'}, status=400)
        
    # OTP Valid -> Execute Logic
    action = context['action']
    target_id = context['target_id']
    extra = context['extra']
    college_id = request.session.get('college_id')
    
    try:
        msg = "Action Complete"
        
        if action == 'student':
            # 1. Get the Main Admin Student Object
            target_student = Student.objects.get(id=target_id)
            target_reg_no = target_student.reg_no
            
            # Identify the Class Name (Crucial for finding the match)
            target_class_name = None
            if target_student.academic_class:
                target_class_name = target_student.academic_class.class_name
            elif target_student.course:
                target_class_name = target_student.course.class_name

            # 2. Soft Delete the Admin Record (Mark Inactive)
            target_student.is_active = False
            target_student.save()
            
            # 3. CRITICAL: Find "Shadow Copies" in Faculty Courses and Delete Them
            notified_faculty_ids = set()

            if target_class_name and target_reg_no:
                # Find any active student with same RegNo in the same Class Name
                shadow_students = Student.objects.filter(
                    reg_no=target_reg_no,
                    course__class_name=target_class_name,
                    is_active=True 
                ).select_related('course__faculty')

                for shadow in shadow_students:
                    # Mark Faculty Copy as Inactive
                    shadow.is_active = False
                    shadow.save()
                    
                    # Collect Faculty ID for cache clearing/notification
                    if shadow.course and shadow.course.faculty:
                        notified_faculty_ids.add(shadow.course.faculty.id)

            # 4. Notify Faculty & Clear Cache (So dashboard updates instantly)
            for fac_id in notified_faculty_ids:
                # Clear Cache
                invalidate_faculty_dashboard_cache(fac_id)
                
                # Send Notification
                try:
                    faculty = NewFaculty.objects.get(id=fac_id)
                    FacultyNotification.objects.create(
                        faculty=faculty,
                        message=f"STUDENT REMOVED - ADMIN UPDATE: Student {target_student.name} ({target_reg_no}) was removed from the roster."
                    )
                except:
                    pass
            
            msg = "Student removed successfully. Faculty rosters synced."
                        
        elif action == 'class':
            # Delete Class (including all associated courses)
            ac_class = AcademicClass.objects.get(id=target_id)
            ac_class.delete()
            invalidate_college_dashboard_cache(college_id)
            msg = "Class deleted successfully."
            
        elif action == 'faculty':
            # Terminate Faculty - Full Logic with Course Reassignment
            faculty = NewFaculty.objects.get(id=target_id)
            college_name = faculty.college_name
            replacement_id = extra.get('replacement_id')
            
            # 1. Delete old Join Requests so they can be invited again later
            FacultyJoinRequest.objects.filter(faculty=faculty, college_id=college_id).delete()

            # 2. Send Faculty Termination Notification
            FacultyNotification.objects.create(
                faculty=faculty,
                message=f"TERMINATION NOTICE: Your association with {college_name} has ended. Contact Admin for details."
            )
            
            try:
                send_mail(
                    f"Termination Notice - {college_name}",
                    f"Dear {faculty.name},\n\nYou have been removed from the faculty list of {college_name}.\nAccess to college data is revoked.\n\nRegards,\nAdmin",
                    "presentsirtechnologies@gmail.com",
                    [faculty.college_email],
                    fail_silently=True
                )
            except:
                pass

            # 3. Handle Course Reassignment or Orphaning
            faculty_courses = Course.objects.filter(faculty=faculty)
            course_count = faculty_courses.count()

            if replacement_id:
                # Transfer to new faculty
                new_faculty = NewFaculty.objects.get(id=replacement_id)
                faculty_courses.update(faculty=None, is_assigned=False)
                
                for course in faculty_courses:
                    # Find the AcademicClass object
                    ac_class = AcademicClass.objects.filter(
                        class_name=course.class_name,
                        department__college_id=college_id
                    ).first()
                    
                    # Find the Subject definition
                    dept_course = DepartmentCourse.objects.filter(
                        course_code=course.subject_code,
                        department__college_id=college_id
                    ).first()

                    if ac_class and dept_course:
                        ClassAssignmentRequest.objects.create(
                            college_id=college_id,
                            faculty=new_faculty,
                            academic_class=ac_class,
                            subject=dept_course,
                            total_hours=course.total_hours,
                            status='Pending'
                        )
                
                # Notify new faculty
                FacultyNotification.objects.create(
                    faculty=new_faculty,
                    message=f"ADMIN REQUEST: You have been nominated to take over classes from {faculty.name}. Please check your Invites."
                )
                msg = f"Faculty terminated. {course_count} reassignment requests sent to {new_faculty.name}."
            else:
                # Orphan classes (Set faculty=None) so data isn't lost
                faculty_courses.update(faculty=None)
                msg = f"Faculty terminated. {course_count} classes are now unassigned (History saved)."

            # 4. Remove Faculty from College Department
            faculty.department_link = None
            faculty.college_name = ""
            faculty.save()

        # Clear Session
        request.session.pop('otp_context', None)
        return JsonResponse({'message': msg})
        
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

def send_add_dept_otp_api(request):
    """Generates OTP and sends to College Admin Email"""
    if request.method != "POST": return JsonResponse({'error': 'POST required'}, status=405)
    
    college_id = request.session.get('college_id')
    if not college_id: return JsonResponse({'error': 'Unauthorized'}, status=401)

    try:
        college = College.objects.get(id=college_id)
        otp = str(secrets.randbelow(900000) + 100000)
        
        # Store in session
        request.session['add_dept_otp'] = otp
        request.session['add_dept_verified'] = False
        
        def send_add_dept_email_bg():
            try:
                send_mail(
                    "Verify Department Creation - Present Sir",
                    f"Your OTP to add a new department is: {otp}",
                    "presentsirtechnologies@gmail.com",
                    [college.admin_email],
                    fail_silently=False
                )
            except Exception as e:
                logger.error(f"Failed to send add dept OTP email: {str(e)}")

        threading.Thread(target=send_add_dept_email_bg).start()
        return JsonResponse({'message': 'OTP sent to admin email.'})
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

def verify_add_dept_otp_api(request):
    """Verifies the OTP stored in session"""
    if request.method != "POST": return JsonResponse({'error': 'POST required'}, status=405)
    
    try:
        data = json.loads(request.body)
        user_otp = data.get('otp', '').strip()
        server_otp = request.session.get('add_dept_otp')
        
        if server_otp and user_otp and hmac.compare_digest(str(user_otp), str(server_otp)):
            request.session['add_dept_verified'] = True
            return JsonResponse({'message': 'Verified'})
        
        return JsonResponse({'error': 'Invalid OTP'}, status=400)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@csrf_exempt
def send_start_sem_otp(request):
    if request.method != "POST": return JsonResponse({'error': 'POST required'}, status=405)
    
    # 1. Store tentative data in Session
    try:
        data = json.loads(request.body)
        college_id = request.session.get('college_id')
        if not college_id: return JsonResponse({'error': 'Unauthorized'}, status=401)

        # Basic Validation
        new_sem = int(data.get('semester'))
        if new_sem < 1 or new_sem > 8:
            return JsonResponse({'error': 'Semester must be between 1 and 8'}, status=400)

        otp = str(secrets.randbelow(900000) + 100000)
        
        request.session['start_sem_context'] = {
            'class_id': data.get('class_id'),
            'new_sem': new_sem,
            'start_date': data.get('start_date'),
            'end_date': data.get('end_date'),
            'otp': otp,
            'timestamp': time.time()
        }
        
        # 2. Send Email
        admin_email = College.objects.get(id=college_id).admin_email
        def send_start_sem_email_bg():
            try:
                send_mail(
                    "Authorize Semester Start - Present Sir",
                    f"OTP to START Semester {new_sem} for this class: {otp}",
                    "presentsirtechnologies@gmail.com",
                    [admin_email],
                    fail_silently=False
                )
            except Exception as e:
                logger.error(f"Failed to send start sem OTP email: {str(e)}")

        threading.Thread(target=send_start_sem_email_bg).start()
        return JsonResponse({'message': 'OTP sent to admin email.'})
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

@csrf_exempt
@transaction.atomic
def verify_start_sem_api(request):
    if request.method != "POST": return JsonResponse({'error': 'POST required'}, status=405)
    
    data = json.loads(request.body)
    user_otp = data.get('otp')
    context = request.session.get('start_sem_context')
    
    if not context or not user_otp or not hmac.compare_digest(str(user_otp), str(context.get('otp'))):
        return JsonResponse({'error': 'Invalid or Expired OTP'}, status=400)
        
    try:
        # 1. Update Class Data
        ac_class = AcademicClass.objects.get(id=context['class_id'])
        new_sem = int(context['new_sem'])
        
        ac_class.current_semester = new_sem
        # Auto-calc Year: 1/2=1, 3/4=2, 5/6=3, 7/8=4
        ac_class.current_year = math.ceil(new_sem / 2)
        
        ac_class.semester_start_date = context['start_date']
        ac_class.semester_end_date = context['end_date']
        ac_class.save()
        
        # 2. Clean Session
        del request.session['start_sem_context']
        
        # 3. Clear Cache
        invalidate_college_dashboard_cache(request.session.get('college_id'))
        
        return JsonResponse({
            'message': f'Semester {new_sem} Started! Class is now in Year {ac_class.current_year}.',
            'new_year': ac_class.current_year
        })
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


# B. END SEMESTER: OTP & EXECUTION
@csrf_exempt
def send_end_sem_otp(request):
    """
    Step 1: Request to End Semester. 
    We validate the class actually HAS an active semester first.
    """
    if request.method != "POST": return JsonResponse({'error': 'POST required'}, status=405)
    
    try:
        data = json.loads(request.body)
        class_id = data.get('class_id')
        college_id = request.session.get('college_id')
        
        ac_class = AcademicClass.objects.get(id=class_id)
        if not ac_class.current_semester:
            return JsonResponse({'error': 'Class is already on Semester Break.'}, status=400)

        otp = str(secrets.randbelow(900000) + 100000)
        request.session['end_sem_context'] = {
            'class_id': class_id,
            'otp': otp,
            'timestamp': time.time()
        }
        
        admin_email = College.objects.get(id=college_id).admin_email
        def send_end_sem_email_bg():
            try:
                send_mail(
                    "Authorize End Semester - Present Sir",
                    f"OTP to END Semester {ac_class.current_semester}: {otp}\n\nWARNING: This will archive all active courses.",
                    "presentsirtechnologies@gmail.com",
                    [admin_email],
                    fail_silently=False
                )
            except Exception as e:
                logger.error(f"Failed to send end sem OTP email: {str(e)}")

        threading.Thread(target=send_end_sem_email_bg).start()
        return JsonResponse({'message': 'OTP sent. Confirming this will archive courses.'})
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

@csrf_exempt
@transaction.atomic
def execute_end_semester(request):
    if request.method != "POST": return JsonResponse({'error': 'POST required'}, status=405)
    
    data = json.loads(request.body)
    user_otp = data.get('otp')
    context = request.session.get('end_sem_context')
    
    if not context or not user_otp or not hmac.compare_digest(str(user_otp), str(context.get('otp'))):
        return JsonResponse({'error': 'Invalid or Expired OTP'}, status=400)

    try:
        ac_class = AcademicClass.objects.get(id=context['class_id'])
        old_sem = ac_class.current_semester
        
        # 1. Archive Active Courses
        # We find courses linked to this class and mark them inactive
        active_courses = Course.objects.filter(
            academic_class=ac_class, 
            is_active=True
        )
        count = active_courses.count()
        
        # Stamp the semester they belonged to before deactivating
        active_courses.update(is_active=False, semester=old_sem)
        
        # 2. Update Class Status
        ac_class.current_semester = None # Set to NULL (Semester Break)
        ac_class.save()
        
        # 3. Clean Session & Cache
        del request.session['end_sem_context']
        invalidate_college_dashboard_cache(request.session.get('college_id'))
        
        return JsonResponse({
            'message': f'Semester {old_sem} Ended. {count} courses archived.',
            'status': 'Break'
        })
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)
    
@csrf_exempt
@transaction.atomic
def archive_class_api(request):
    """
    Marks a class as Alumni (Inactive).
    1. Sets AcademicClass.is_active = False
    2. Sets ALL Students in that class to is_active = False
    """
    if request.method != "POST": return JsonResponse({}, status=405)
    
    # Verify OTP using the existing context logic
    user_otp = json.loads(request.body).get('otp')
    context = request.session.get('otp_context')
    
    if not context or not user_otp or not hmac.compare_digest(str(user_otp), str(context.get('otp'))) or context.get('action') != 'archive_class':
        return JsonResponse({'error': 'Invalid or Expired OTP'}, status=400)

    target_id = context['target_id']
    college_id = request.session.get('college_id')

    try:
        ac_class = AcademicClass.objects.get(id=target_id)
        
        # 1. Deactivate Class
        ac_class.is_active = False
        ac_class.save()
        
        # 2. Deactivate All Students in this class
        Student.objects.filter(academic_class=ac_class).update(is_active=False)
        
        # 3. Clear Cache
        invalidate_college_dashboard_cache(college_id)
        
        # Reset Session
        request.session.pop('otp_context', None)
        
        return JsonResponse({'message': f"Class marked as Alumni. Student roster deactivated."})
        
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)
