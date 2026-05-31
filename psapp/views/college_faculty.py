from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.db import transaction
from django.core.mail import send_mail
from psapp.models import NewFaculty, FacultyJoinRequest, FacultyNotification, College, Course, AcademicClass, DepartmentCourse, ClassAssignmentRequest
import json, logging

logger = logging.getLogger(__name__)

@csrf_exempt
def search_faculty_api(request):
    query = request.GET.get('q', '').lower()
    faculties = NewFaculty.objects.filter(college_email__icontains=query)[:5]
    return JsonResponse({'results': [{'id': f.id, 'name': f.name, 'email': f.college_email} for f in faculties]}) # pyright: ignore[reportAttributeAccessIssue]

@csrf_exempt
def search_faculty_by_id_api(request):
    try:
        faculty = NewFaculty.objects.get(faculty_reg_id=request.GET.get('reg_id', '').strip())
        return JsonResponse({'found': True, 'id': faculty.id, 'name': faculty.name, 'email': faculty.college_email}) # pyright: ignore[reportAttributeAccessIssue]
    except NewFaculty.DoesNotExist:
        return JsonResponse({'found': False})

def assign_faculty_api(request):
    if request.method != "POST": return JsonResponse({}, status=405)
    faculty = NewFaculty.objects.get(id=request.POST.get('faculty_id'))
    faculty.department_link_id = request.POST.get('dept_id') # pyright: ignore[reportAttributeAccessIssue]
    faculty.save()
    return JsonResponse({'message': 'Faculty Assigned'})

@csrf_exempt
def send_faculty_invite_api(request):
    if request.method != "POST": 
        return JsonResponse({'error': 'POST required'}, status=405)
    
    try:
        data = json.loads(request.body)
        
        # 1. Get College ID
        college_id = request.session.get('college_id')
        if not college_id:
            return JsonResponse({'error': 'Session expired. Please log in again.'}, status=401)

        faculty_db_id = data.get('faculty_db_id')
        dept_id = data.get('dept_id')
        
        if not faculty_db_id or not dept_id:
            return JsonResponse({'error': 'Missing Faculty ID or Dept ID.'}, status=400)

        # 2. Check if Faculty is ALREADY WORKING elsewhere
        target_faculty = NewFaculty.objects.get(id=faculty_db_id)
        if target_faculty.department_link:
            # If they are linked to a department, they belong to a college
            current_college = target_faculty.department_link.college.college_name
            return JsonResponse({
                'error': f"Cannot invite. This faculty is currently employed at {current_college}. They must leave that college first."
            }, status=400)

        # 3. Check for Pending Invites (Existing Logic)
        exists = FacultyJoinRequest.objects.filter(
            college_id=college_id, 
            faculty_id=faculty_db_id,
            status__in=['Pending', 'Approved']
        ).exists()

        if exists:
            return JsonResponse({'error': 'Invitation already sent or faculty joined.'}, status=400)

        # 4. Create Request
        FacultyJoinRequest.objects.create(
            college_id=college_id,
            department_id=dept_id,
            faculty_id=faculty_db_id,
            status='Pending'
        )
        
        # 5. Notify
        FacultyNotification.objects.create(
            faculty_id=faculty_db_id,
            message=f"New Job Offer from {College.objects.get(id=college_id).college_name}."
        )

        return JsonResponse({'message': 'Invitation sent successfully!'})

    except NewFaculty.DoesNotExist:
        return JsonResponse({'error': 'Faculty not found'}, status=404)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

@csrf_exempt
def get_faculty_details_admin(request):
    fac_id = request.GET.get('faculty_id')
    try:
        faculty = NewFaculty.objects.get(id=fac_id)
        courses = Course.objects.filter(faculty=faculty)
        
        # --- FIX: Send detailed objects instead of just strings ---
        course_data = []
        for c in courses:
            course_data.append({
                'title': f"{c.subject_name} ({c.class_name})",
                'is_official': c.is_assigned  # True = Admin Assigned, False = Self Created
            })
        
        return JsonResponse({
            'id': faculty.id, 
            'name': faculty.name,
            'email': faculty.college_email,
            'assigned_courses': course_data # Sending the structured list
        })
    except NewFaculty.DoesNotExist:
        return JsonResponse({'error': 'Not found'}, status=404)

@csrf_exempt
@transaction.atomic
def terminate_faculty_api(request):
    if request.method != "POST": return JsonResponse({}, status=405)
    data = json.loads(request.body)
    fac_id = data.get('faculty_id')
    replacement_id = data.get('replacement_id') # <--- New Parameter
    
    try:
        faculty = NewFaculty.objects.get(id=fac_id)
        college_id = request.session.get('college_id')
        college_name = faculty.college_name
        
        # 1. FIX REJOINING: Delete old Join Requests so they can be invited again later
        FacultyJoinRequest.objects.filter(faculty=faculty, college_id=college_id).delete()

        # 2. NOTIFY FACULTY (Email + Dashboard)
        # Dashboard Notification
        FacultyNotification.objects.create(
            faculty=faculty,
            message=f"TERMINATION NOTICE: Your association with {college_name} has ended. Contact Admin for details."
        )
        # Email Notification (Silently fail if network issue)
        try:
            send_mail(
                f"Termination Notice - {college_name}",
                f"Dear {faculty.name},\n\nYou have been removed from the faculty list of {college_name}.\nAccess to college data is revoked.\n\nRegards,\nAdmin",
                "presentsirtechnologies@gmail.com",
                [faculty.college_email],
                fail_silently=True
            )
        except Exception as e:
            logger.exception(f"Error sending termination email to {faculty.college_email}: {str(e)}")

        # 3. FIX RECORDS: Reassign or Orphan Classes (Don't Delete!)
        faculty_courses = Course.objects.filter(faculty=faculty)
        course_count = faculty_courses.count()

        if replacement_id:
            # Transfer to new faculty
            new_faculty = NewFaculty.objects.get(id=replacement_id)
            faculty_courses.update(faculty=None, is_assigned=False)
            for course in faculty_courses:
                # Find the 'AcademicClass' object needed for the request
                # We assume course.class_name matches an AcademicClass name in this college
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
            # Orphan them (Set faculty=None) so data isn't lost
            faculty_courses.update(faculty=None)
            msg = f"Faculty terminated. {course_count} classes are now unassigned (History saved)."

        # 4. Remove Faculty from College Dept
        faculty.department_link = None
        faculty.college_name = "" 
        faculty.save()
        
        return JsonResponse({'message': msg})

    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON data provided'}, status=400)
    except NewFaculty.DoesNotExist:
        return JsonResponse({'error': 'Faculty member not found'}, status=404)
    except Exception as e:
        logger.exception(f"Unexpected error terminating faculty: {str(e)}")
        return JsonResponse({'error': 'An unexpected error occurred while terminating the faculty member'}, status=500)

