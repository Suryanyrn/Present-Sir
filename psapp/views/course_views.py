from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.db import transaction
from psapp.models import DepartmentCourse, Course, AcademicClass, ClassAssignmentRequest, FacultyNotification, Student, NewFaculty
from .utils import invalidate_college_dashboard_cache, invalidate_faculty_dashboard_cache
import json, logging

logger = logging.getLogger(__name__)

def add_dept_course_api(request):
    if request.method != "POST": return JsonResponse({'error': 'POST required'}, status=405)
    
    try:
        dept_id = request.POST.get('dept_id')
        course_code = request.POST.get('course_code', '').strip().upper()
        course_title = request.POST.get('course_title', '').strip()
        semester = request.POST.get('semester')
        course_type = request.POST.get('course_type')

        if not dept_id or not course_code or not course_title:
            return JsonResponse({'error': 'All fields are required'}, status=400)

        # Check if course code already exists in this department
        if DepartmentCourse.objects.filter(department_id=dept_id, course_code__iexact=course_code).exists():
            return JsonResponse({'error': f'Subject code "{course_code}" already exists in this department.'}, status=400)

        DepartmentCourse.objects.create(
            department_id=dept_id,
            course_name=course_title,
            course_code=course_code,
            semester=semester,
            course_type=course_type
        )
        return JsonResponse({'message': 'Course Added Successfully'})
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

@csrf_exempt
def get_dept_courses_api(request):
    dept_id = request.GET.get('dept_id')
    try:
        # 1. Fetch All
        courses = DepartmentCourse.objects.filter(department_id=dept_id)
        
        data = []
        for c in courses:
            # Logic: If Elective, force semester to be 'Electives' category
            sem_display = c.semester if c.course_type != 'Elective' else 999 # 999 ensures it goes last
            
            data.append({
                'id': c.id, 
                'title': c.course_name, 
                'code': c.course_code,
                'semester': c.semester if c.course_type != 'Elective' else 'Elective',
                'sort_key': sem_display, # Internal sorting key
                'type': c.course_type
            })
            
        # Sort in Python: Sem 1, 2... then Electives (999)
        data.sort(key=lambda x: (x['sort_key'], x['title']))
        
        return JsonResponse({'courses': data})
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)
    dept_id = request.GET.get('dept_id')
    semester = request.GET.get('semester')
    try:
        courses = DepartmentCourse.objects.filter(department_id=dept_id).order_by('semester', 'course_name')
        # FIX: Include semester and course_type in response
        query = DepartmentCourse.objects.filter(department_id=dept_id)
        
        # If semester provided, filter by it. If not, return all (fallback)
        if semester:
            query = query.filter(semester=semester)
            
        courses = query.order_by('semester', 'course_name')
        data = [{
            'id': c.id, 
            'title': c.course_name, 
            'code': c.course_code,
            'semester': c.semester, 
            'type': c.course_type
        } for c in courses]
        return JsonResponse({'courses': data})
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)
    
@csrf_exempt
def delete_dept_course_api(request):
    if request.method != "POST": return JsonResponse({'error': 'POST required'}, status=405)
    course_id = request.POST.get('course_id')
    try:
        DepartmentCourse.objects.get(id=course_id).delete()
        return JsonResponse({'message': 'Subject deleted successfully'})
    except DepartmentCourse.DoesNotExist:
        return JsonResponse({'error': 'Subject not found'}, status=404)

@csrf_exempt
def edit_dept_course_api(request):
    if request.method != "POST": return JsonResponse({'error': 'POST required'}, status=405)
    try:
        course = DepartmentCourse.objects.get(id=request.POST.get('course_id'))
        course.course_name = request.POST.get('course_title')
        course.course_code = request.POST.get('course_code')
        # Update additional fields if provided
        if request.POST.get('semester'):
            course.semester = request.POST.get('semester')
        if request.POST.get('course_type'):
            course.course_type = request.POST.get('course_type')
        course.save()
        return JsonResponse({'message': 'Subject updated successfully'})
    except DepartmentCourse.DoesNotExist:
        return JsonResponse({'error': 'Subject not found'}, status=404)

@csrf_exempt
def assign_subject_to_class_api(request):
    if request.method != "POST": 
        return JsonResponse({'error': 'POST required'}, status=405)
    
    try:
        data = json.loads(request.body)
        class_id = data.get('class_id')
        subject_id = data.get('subject_id')
        faculty_id = data.get('faculty_id')
        total_hours = data.get('total_hours')
        college_id = request.session.get('college_id')

        # 1. Fetch Objects
        subject_obj = DepartmentCourse.objects.get(id=subject_id)
        class_obj = AcademicClass.objects.get(id=class_id)
        
        # 2. Check if this Faculty is ALREADY teaching this exact class
        if Course.objects.filter(
            class_name=class_obj.class_name, 
            subject_code=subject_obj.course_code, 
            faculty_id=faculty_id
        ).exists():
            return JsonResponse({'error': 'This faculty is already teaching this class.'}, status=400)

        # 3. Check if Another Faculty is teaching it (Conflict)
        existing_active_course = Course.objects.filter(
            class_name=class_obj.class_name, 
            subject_code=subject_obj.course_code,
            faculty__isnull=False 
        ).exclude(faculty_id=faculty_id).first()

        if existing_active_course:
            # --- FIX: Safe Access to Faculty Name ---
            current_fac_name = "Unknown Faculty"
            if existing_active_course.faculty:
                current_fac_name = existing_active_course.faculty.name
            
            return JsonResponse({'error': f'Class is currently assigned to {current_fac_name}. Revoke first.'}, status=400)

        existing_req = ClassAssignmentRequest.objects.filter(
            academic_class_id=class_id,
            subject_id=subject_id,
            status__in=['Pending', 'Approved']
        ).exclude(faculty_id=faculty_id).first()

        if existing_req:
            try:
                existing_fac_name = existing_req.faculty.name if existing_req.faculty else 'Unassigned'
            except Exception:
                existing_fac_name = 'Another Faculty'

            if existing_req.status == 'Approved':
                return JsonResponse({'error': f'Class is currently assigned to {existing_fac_name}. Revoke first.'}, status=400)
            else:
                return JsonResponse({'error': f'An assignment request is already pending for {existing_fac_name}.'}, status=400)

        # 6. CLEANUP: Terminate old 'Approved' requests if they aren't active
        ClassAssignmentRequest.objects.filter(
            academic_class_id=class_id,
            subject_id=subject_id,
            faculty_id=faculty_id,
            status='Approved'
        ).update(status='Terminated')

        # 6. Check for Reassignment Context
        is_reassignment = Course.objects.filter(
            class_name=class_obj.class_name,
            subject_code=subject_obj.course_code,
            faculty__isnull=True
        ).exists()

        # 7. Create Request
        ClassAssignmentRequest.objects.create(
            college_id=college_id,
            academic_class_id=class_id,
            subject_id=subject_id,
            faculty_id=faculty_id,
            total_hours=total_hours,
            status='Pending'
        )

        msg = f"New Assignment Request: {subject_obj.course_name}."
        if is_reassignment:
            msg = f"REASSIGNMENT REQUEST: Take over '{subject_obj.course_name}' for {class_obj.class_name} (History linked)."

        FacultyNotification.objects.create(
            faculty_id=faculty_id,
            message=msg
        )

        return JsonResponse({'message': 'Approval request sent successfully.'})

    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

def revoke_course_api(request):
    if request.method != "POST": return JsonResponse({'error': 'POST required'}, status=405)
    
    course_id = request.POST.get('course_id') # The ID of the Faculty's Course object
    college_id = request.session.get('college_id')
    
    try:
        # 1. Get the course (Verify it belongs to this college via dept link)
        course = Course.objects.get(id=course_id, faculty__department_link__college_id=college_id)
        
        # 2. Free up the Assignment Request (so it can be re-assigned)
        reqs = ClassAssignmentRequest.objects.filter(
            faculty=course.faculty,
            subject__course_code=course.subject_code,
            academic_class__class_name=course.class_name,
            status='Approved'
        )
        for req in reqs:
            req.status = 'Revoked'
            req.save()

        # 3. Notify Faculty
        FacultyNotification.objects.create(
            faculty=course.faculty,
            message=f"Admin has revoked your assignment for {course.subject_name} ({course.class_name})."
        )

        course.faculty = None
        course.save()
        
        return JsonResponse({'message': 'Assignment revoked. Data preserved as Unassigned.'})
    except Course.DoesNotExist:
        return JsonResponse({'error': 'Course not found or unauthorized.'}, status=404)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

@csrf_exempt
def get_class_assigned_courses_api(request):
    """Updated to include Course Type and Batch Name"""
    class_id = request.GET.get('class_id')
    try:
        ac_class = AcademicClass.objects.get(id=class_id)
        
        # Fetch courses linked to this AcademicClass
        assigned_courses = Course.objects.filter(
            academic_class=ac_class,
            is_active=True
        ).select_related('faculty')

        data = []
        for c in assigned_courses:
            fac_name = c.faculty.name if c.faculty else "Unassigned"
            
            # Count only active enrolled students for this specific batch
            student_count = c.enrolled_students.filter(is_active=True).count()

            data.append({
                'id': c.id,
                'subject': c.subject_name,
                'code': c.subject_code,
                'type': c.course_type, # Core, Lab, Elective
                'batch': c.batch_name, # Main, Group A, etc.
                'faculty': fac_name,
                'hours': c.total_hours,
                'student_count': student_count
            })
            
        return JsonResponse({'courses': data})
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

@transaction.atomic
@csrf_exempt
def assign_special_course_api(request):
    """
    Handles assignment for Electives and Labs.
    FIX: Now only creates an Invite (Request). Course is created ONLY when faculty accepts.
    """
    if request.method != "POST": 
        return JsonResponse({'error': 'POST required'}, status=405)
    
    try:
        data = json.loads(request.body)
        
        # 1. Extract Data
        college_id = request.session.get('college_id')
        parent_class_id = data.get('class_id') 
        subject_id = data.get('subject_id')
        faculty_id = data.get('faculty_id')
        student_ids = data.get('student_ids', []) # List of IDs [1, 20, 45]
        
        batch_name = data.get('batch_name') # "Group A"
        total_hours = data.get('total_hours', 45)
        
        if not student_ids:
            return JsonResponse({'error': 'No students selected.'}, status=400)

        # 2. Validation
        subject = DepartmentCourse.objects.get(id=subject_id)
        faculty = NewFaculty.objects.get(id=faculty_id)
        ac_class = AcademicClass.objects.get(id=parent_class_id)
        
        # Check if a pending request already exists for this exact setup
        if ClassAssignmentRequest.objects.filter(
            faculty=faculty,
            subject=subject,
            academic_class=ac_class,
            batch_name=batch_name,
            status='Pending'
        ).exists():
            return JsonResponse({'error': 'An invite for this batch is already pending.'}, status=400)

        # 3. Create Assignment Request (Store students in JSON)
        ClassAssignmentRequest.objects.create(
            college_id=college_id,
            faculty=faculty,
            academic_class=ac_class,
            subject=subject,
            total_hours=total_hours,
            batch_name=batch_name, 
            student_list_json=json.dumps(student_ids), # <--- Storing IDs here
            status='Pending'
        )
        
        # 4. Notify Faculty
        FacultyNotification.objects.create(
            faculty=faculty,
            message=f"NEW ASSIGNMENT: {subject.course_type} '{subject.course_name}' ({batch_name}). Please check Invites."
        )
        
        # 5. Clear Caches
        invalidate_college_dashboard_cache(college_id)
        
        return JsonResponse({
            'message': f'Invite sent to {faculty.name} for {subject.course_name} ({len(student_ids)} students).'
        })

    except Exception as e:
        logger.exception("Assign Special Course Error")
        return JsonResponse({'error': str(e)}, status=500)
    """
    Handles assignment for Electives and Labs.
    Creates a Course linked to specific students and sends an invite.
    """
    if request.method != "POST": 
        return JsonResponse({'error': 'POST required'}, status=405)
    
    try:
        data = json.loads(request.body)
        
        # 1. Extract Data
        college_id = request.session.get('college_id')
        dept_id = data.get('dept_id') # To find the subject
        parent_class_id = data.get('class_id') # The main class (e.g. B.Tech CSE)
        subject_id = data.get('subject_id')
        faculty_id = data.get('faculty_id')
        student_ids = data.get('student_ids', []) # List of selected IDs
        
        batch_name = data.get('batch_name') # "Group A"
        total_hours = data.get('total_hours', 45)
        
        if not student_ids:
            return JsonResponse({'error': 'No students selected.'}, status=400)

        # 2. Get Objects
        subject = DepartmentCourse.objects.get(id=subject_id)
        faculty = NewFaculty.objects.get(id=faculty_id)
        ac_class = AcademicClass.objects.get(id=parent_class_id)
        
        # 3. Create the Course
        # We link it to the AcademicClass so it shows up in the Admin Dashboard
        new_course = Course.objects.create(
            academic_class=ac_class, # Link to Parent
            faculty=faculty,
            class_name=ac_class.class_name,  # FIX: Set class_name for consistency
            subject_name=subject.course_name,
            subject_code=subject.course_code,
            course_type=subject.course_type, # 'Elective' or 'Lab'
            batch_name=batch_name,
            total_hours=total_hours,
            is_assigned=True, # It IS assigned by admin
            is_active=True
        )
        
        # 4. Link Selected Students (M2M)
        # We fetch the actual student objects to ensure validity
        selected_students = Student.objects.filter(id__in=student_ids, college_id=college_id)
        new_course.enrolled_students.set(selected_students)
        
        # 5. Create Assignment Request (So faculty can Accept/Reject)
        ClassAssignmentRequest.objects.create(
            college_id=college_id,
            faculty=faculty,
            academic_class=ac_class,
            subject=subject,
            total_hours=total_hours,
            status='Pending'
        )
        
        # 6. Notify Faculty
        FacultyNotification.objects.create(
            faculty=faculty,
            message=f"NEW ASSIGNMENT: {subject.course_type} '{subject.course_name}' ({batch_name}). Please check Invites."
        )
        
        # Clear Caches
        invalidate_college_dashboard_cache(college_id)
        invalidate_faculty_dashboard_cache(faculty_id)
        
        return JsonResponse({
            'message': f'{subject.course_type} assigned successfully to {len(selected_students)} students.'
        })

    except Exception as e:
        logger.exception("Assign Special Course Error")
        return JsonResponse({'error': str(e)}, status=500)
    
@csrf_exempt
def get_dept_students_for_selection_api(request):
    dept_id = request.GET.get('dept_id')
    classes = AcademicClass.objects.filter(department_id=dept_id).order_by('current_year', 'class_name', 'section')
    
    data = []
    for cls in classes:
        students = Student.objects.filter(academic_class=cls, is_active=True).values('id', 'reg_no', 'name')
        data.append({
            'class_id': cls.id,
            # Group Name includes Section now
            'class_name': f"{cls.class_name} - Sec {cls.section} (Year {cls.current_year})",
            'students': list(students)
        })
    return JsonResponse({'classes': data})

@csrf_exempt
def get_class_assigned_courses_for_export_api(request):
    """
    API to populate the 'Select Subject' dropdown in Admin Reports.
    Returns: List of courses for a specific class.
    """
    college_id = request.session.get('college_id')
    if not college_id:
        return JsonResponse({'error': 'Unauthorized'}, status=401)

    class_id = request.GET.get('class_id')
    if not class_id:
        return JsonResponse({'error': 'Class ID required'}, status=400)
    
    try:
        ac_class = AcademicClass.objects.get(id=class_id)
        # Fetch all courses (Active & Inactive) so we can print reports for old courses too
        courses = Course.objects.filter(class_name=ac_class.class_name).order_by('subject_name')
        
        course_list = [{
            'id': c.id,
            'title': c.subject_name,
            'code': c.subject_code,
            'faculty': c.faculty.name if c.faculty else 'Unassigned'
        } for c in courses]
        
        return JsonResponse({'courses': course_list})
    except AcademicClass.DoesNotExist:
        return JsonResponse({'error': 'Class not found'}, status=404)
    except Exception as e:
        logger.exception(f"Error fetching export courses: {str(e)}")
        return JsonResponse({'error': str(e)}, status=500)
