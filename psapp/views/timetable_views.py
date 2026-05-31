from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from datetime import datetime, timedelta
import math, json, logging
from psapp.models import AcademicClass, TimeTableSlot, TimeTableSettings, DepartmentCourse, Course

logger = logging.getLogger(__name__)

def calculate_semester_stats_api(request):
    if request.method != "POST": return JsonResponse({}, status=405)
    data = json.loads(request.body)
    
    start_str = data.get('start_date')
    end_str = data.get('end_date')
    # days_config: [0,1,2,3,4] where 0=Mon, 6=Sun
    active_days = data.get('active_days', [0,1,2,3,4]) 
    
    start_date = datetime.strptime(start_str, "%Y-%m-%d").date()
    end_date = datetime.strptime(end_str, "%Y-%m-%d").date()
    
    total_days = (end_date - start_date).days + 1
    working_days_count = 0
    
    for i in range(total_days):
        current_day = start_date + timedelta(days=i)
        if current_day.weekday() in active_days:
            working_days_count += 1
            
    # Calculate Weeks (Roughly)
    total_weeks = working_days_count / len(active_days)
    
    return JsonResponse({
        'working_days': working_days_count,
        'total_weeks': round(total_weeks, 1),
        'message': f"Approx {round(total_weeks, 1)} instructional weeks available."
    })
    
# --- CORRECTED init_timetable_api ---
@csrf_exempt
def init_timetable_api(request):
    class_id = request.GET.get('class_id')
    if not class_id or class_id == 'null' or class_id == 'undefined':
        return JsonResponse({'error': 'Invalid Class ID provided.'}, status=400)
    
    try:
        ac_class = AcademicClass.objects.get(id=class_id)
        
        # 1. Get Settings
        settings, created = TimeTableSettings.objects.get_or_create(
            academic_class=ac_class,
            defaults={
                'semester_start': datetime.today().date(),
                'semester_end': (datetime.today() + timedelta(days=90)).date(),
                'working_days': '["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]',
                'periods_per_day': 7
            }
        )

        # 2. Date Calcs (Existing logic)
        start_date = settings.semester_start
        end_date = settings.semester_end
        if isinstance(start_date, str): start_date = datetime.strptime(start_date, "%Y-%m-%d").date()
        if isinstance(end_date, str): end_date = datetime.strptime(end_date, "%Y-%m-%d").date()
        total_days = (end_date - start_date).days
        weeks = max(1, math.ceil(total_days / 7))

        current_year = ac_class.current_year
        valid_semesters = [(current_year * 2) - 1, current_year * 2] # e.g., Year 2 gives [3, 4]
        valid_codes = DepartmentCourse.objects.filter(
            department=ac_class.department, 
            semester__in=valid_semesters
        ).values_list('course_code', flat=True)
        courses = Course.objects.filter(class_name=ac_class.class_name,subject_code__in=valid_codes)
        subject_load = []
        active_codes = []

        for c in courses:
            fac_name = c.faculty.name if c.faculty else "Unassigned"
            fac_id = c.faculty.id if c.faculty else None
            
            safe_weeks = weeks if (weeks is not None and weeks > 0) else 1
            weekly_hours = round(c.total_hours / safe_weeks)
            
            subject_load.append({
                'id': c.id, 
                'name': c.subject_name,
                'code': c.subject_code,
                'faculty': fac_name,
                'faculty_id': fac_id,
                'color': '#0d9488', 
                'total_hours': c.total_hours,
                'weekly_hours_needed': max(1, weekly_hours),
                'status': 'active'
            })
            active_codes.append(c.subject_code)

        # --- 5. Get Missing Department Subjects (Status: Unassigned) ---
        if ac_class.department: 
            # FIX: Filter by Department AND Valid Semesters
            dept_courses = DepartmentCourse.objects.filter(
                department=ac_class.department,
                semester__in=valid_semesters # <--- KEY FILTER
            )
            
            for dc in dept_courses:
                # Don't show duplicates if it's already active
                if dc.course_code not in active_codes:
                    subject_load.append({
                        'id': None,
                        'name': dc.course_name,
                        'code': dc.course_code,
                        'faculty': 'Not Assigned',
                        'faculty_id': None,
                        'color': '#64748b',
                        'total_hours': 0,
                        'weekly_hours_needed': 0,
                        'status': 'unassigned'
                    })

        # 6. Fetch Slots
        slots = TimeTableSlot.objects.filter(academic_class=ac_class).values('day', 'period_number', 'subject_id', 'subject__subject_code')

        return JsonResponse({
            'start': start_date.strftime("%Y-%m-%d"),
            'end': end_date.strftime("%Y-%m-%d"),
            'working_days': settings.get_working_days(),
            'periods': settings.periods_per_day,
            'weeks_available': weeks,
            'subjects': subject_load,
            'existing_slots': list(slots)
        })
    except Exception as e:
        logger.exception(f"Timetable Init Error: {e}") 
        return JsonResponse({'error': str(e)}, status=500)    

@csrf_exempt
def check_faculty_conflict_api(request):
    # Checks if Faculty is busy in ANY OTHER class at this time
    if request.method != "POST": return JsonResponse({}, status=405)
    
    try:
        data = json.loads(request.body)
        faculty_id = data.get('faculty_id')
        day = data.get('day')
        period = data.get('period')
        current_class_id = data.get('class_id')
        
        # If no faculty is assigned to the subject, there can't be a personal conflict
        if not faculty_id: 
            return JsonResponse({'conflict': False}) 

        # Search for this faculty in slots of OTHER classes
        # We look for slots where the subject's faculty ID matches
        conflict = TimeTableSlot.objects.filter(
            subject__faculty_id=faculty_id,
            day=day,
            period_number=period
        ).exclude(academic_class_id=current_class_id).first()
        
        if conflict:
            # --- FIX: Safe string construction ---
            # Even if we found a conflict slot, we must carefully get names
            # because relations could theoretically be broken/null
            
            fac_name = "Unknown Faculty"
            class_name = "Unknown Class"
            subject_name = "Unknown Subject"

            if conflict.academic_class:
                class_name = conflict.academic_class.class_name
            
            if conflict.subject:
                subject_name = conflict.subject.subject_name
                if conflict.subject.faculty:
                    fac_name = conflict.subject.faculty.name
            
            return JsonResponse({
                'conflict': True, 
                'message': f"Conflict: {fac_name} is already teaching {subject_name} in {class_name} at this time."
            })
            
        return JsonResponse({'conflict': False})

    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

@csrf_exempt
def save_timetable_slot_api(request):
    if request.method != "POST": return JsonResponse({}, status=405)
    
    try:
        data = json.loads(request.body)
        
        # Now this works because the Model has 'is_break'
        TimeTableSlot.objects.update_or_create(
            academic_class_id=data['class_id'],
            day=data['day'],
            period_number=data['period'],
            defaults={
                'subject_id': data['subject_id'],
                'is_break': False 
            }
        )
        return JsonResponse({'message': 'Saved'})
        
    except Exception as e:
        logger.exception(f"Save Slot Error: {e}")

def save_timetable_settings_api(request):
    if request.method != "POST": return JsonResponse({}, status=405)
    data = json.loads(request.body)
    
    class_id = data.get('class_id')
    if not class_id:
        return JsonResponse({'error': 'Class ID required.'}, status=400)

    try:
        settings = TimeTableSettings.objects.get(academic_class_id=class_id)
        
        # 1. Update Dates & Periods
        settings.semester_start = datetime.strptime(data['start_date'], "%Y-%m-%d").date()
        settings.semester_end = datetime.strptime(data['end_date'], "%Y-%m-%d").date()
        settings.periods_per_day = int(data['periods'])
        
        # 2. Update Working Days (using the helper)
        settings.set_working_days(data.get('working_days', [])) 
        
        settings.save()

        return JsonResponse({'message': 'Timetable settings saved successfully.'})
    
    except TimeTableSettings.DoesNotExist:
        return JsonResponse({'error': 'Settings not found for this class.'}, status=404)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

@csrf_exempt
def get_suggested_session_api(request):
    """Checks Timetable to see if this faculty has a class right now"""
    course_id = request.GET.get('course_id')
    date_str = request.GET.get('date') # YYYY-MM-DD
    
    try:
        target_course = Course.objects.get(id=course_id)
        
        # 1. Determine Day of Week (e.g., "Monday")
        date_obj = datetime.strptime(date_str, "%Y-%m-%d")
        day_name = date_obj.strftime("%A")
        
        # 2. Check TimeTableSlot for this Class + Day + Subject
        # We need the AcademicClass ID. We can infer it from the course name and dept
        # Or simpler: Find slots for this subject ID (if subject is linked properly)
        
        # Ideally, we find the slot by matching Subject Code and Class Name
        slots = TimeTableSlot.objects.filter(
            academic_class__class_name=target_course.class_name,
            day=day_name,
            subject__subject_code=target_course.subject_code
        ).values_list('period_number', flat=True)
        
        if slots:
            # If multiple slots (e.g. 1, 2), return the range
            return JsonResponse({
                'found': True,
                'start': min(slots),
                'end': max(slots),
                'message': f"Timetable found: Period {min(slots)}-{max(slots)}"
            })
            
        return JsonResponse({'found': False})
        
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)
