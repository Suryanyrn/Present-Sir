from django.http import HttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.db.models import Sum, Count, Q
from psapp.models import Course, AttendanceRecord, AttendanceSession, AcademicClass, Student, NewFaculty
from django.db import transaction
import csv, json, logging

logger = logging.getLogger(__name__)

def export_attendance_csv(request, course_id):
    """Faculty Export CSV - Day-wise format with S.No, Reg No, Name, Date (Session), Present, OD, Absent, %"""
    faculty_id = request.session.get('faculty_id')
    if not faculty_id: return HttpResponse("Unauthorized", status=401)

    try:
        course = Course.objects.get(id=course_id)
        sessions = course.sessions.all().order_by('date', 'start_session')
        
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = f'attachment; filename="{course.subject_name}_{course.class_name}_Report.csv"'

        writer = csv.writer(response)
        
        # Headers: S.No, Reg No, Name, Date (Session), Total Present, Total OD, Total Absent, Percentage
        session_headers = [f"{s.date.strftime('%d-%m')} (S{s.start_session}-S{s.end_session})" for s in sessions]
        writer.writerow(['S.No', 'Reg No', 'Name'] + session_headers + ['Total Present', 'Total OD', 'Total Absent', 'Percentage'])

        # FIX: Fetch only active students via M2M enrolled_students relationship
        students = course.enrolled_students.filter(is_active=True).order_by('reg_no')
        records_map = {(r.student_id, r.session_id): r.status for r in AttendanceRecord.objects.filter(session__in=sessions)} # pyright: ignore[reportAttributeAccessIssue]

        for idx, student in enumerate(students, 1):
            row = [idx, student.reg_no, student.name]
            p_hours = 0
            od_hours = 0
            a_hours = 0
            total_hours_possible = 0
            
            for session in sessions:
                status = records_map.get((student.id, session.id), '-')
                row.append(status)
                dur = int(session.session_duration) if session.session_duration else 0
                total_hours_possible += dur

                if status == 'Present': 
                    p_hours += dur
                elif status == 'OD': 
                    od_hours += dur
                elif status == 'Absent': 
                    a_hours += dur

            eff_present = p_hours + od_hours
            pct = int((eff_present / total_hours_possible) * 100) if total_hours_possible > 0 else 0
            row.extend([p_hours, od_hours, a_hours, f"{pct}%"])
            writer.writerow(row)

        return response
    except Course.DoesNotExist:
        return HttpResponse("Class not found", status=404)
    except Exception as e:
        logger.exception(f"Error exporting attendance CSV for course {course_id}: {str(e)}")
        return HttpResponse("Error generating attendance report", status=500)

@csrf_exempt
def get_class_analytics_api(request):
    class_id = request.GET.get('class_id')
    course_id = request.GET.get('course_id')
    
    try:
        # --- A. CONTEXT SETUP ---
        faculty_name = "" 
        title = ""
        subtitle = ""
        
        if course_id:
            # === SUBJECT VIEW (Faculty Mode) ===
            target_course = Course.objects.get(id=course_id)
            title = f"{target_course.subject_name}"
            subtitle = f"{target_course.class_name}"
            
            faculty_name = target_course.faculty.name if target_course.faculty else "Unassigned"

            sessions_qs = AttendanceSession.objects.filter(course=target_course).order_by('date')
            students = target_course.enrolled_students.all()
        else:
            # === OVERALL CLASS VIEW (Admin Mode) ===
            academic_class = AcademicClass.objects.get(id=class_id)
            title = f"{academic_class.class_name}"
            subtitle = f"Overall Performance"
            faculty_name = "Class Aggregate" 

            # Filter only official courses for this class
            sessions_qs = AttendanceSession.objects.filter(
                course__academic_class=academic_class, # Link to actual class object
                course__is_personal=False
            ).order_by('date')
            
            students = Student.objects.filter(academic_class=academic_class, is_active=True)

        # --- B. CALCULATE HOURS ---
        total_sessions_count = sessions_qs.count()
        # Sum of all session durations
        total_hours_taught = sessions_qs.aggregate(t=Sum('session_duration'))['t'] or 0

        # --- C. STUDENT STATS (The Crash Proof Loop) ---
        all_records = AttendanceRecord.objects.filter(
            session__in=sessions_qs
        ).select_related('student', 'session')
        
        # 1. Initialize Map with CURRENT Active Students
        # usage: { reg_no: { obj, present, total } }
        student_map = {
            s.reg_no: {'obj': s, 'present_hours': 0, 'total_hours': 0} 
            for s in students
        }

        # 2. Iterate Records
        for record in all_records:
            reg = record.student.reg_no
            
            # CRITICAL FIX: Handle students not in the map (e.g., Deleted Students)
            if reg not in student_map:
                # Decide: Do we skip them or add them? 
                # Let's add them so the stats are accurate for history.
                student_map[reg] = {
                    'obj': record.student,
                    'present_hours': 0,
                    'total_hours': 0
                }
            
            # Increment Total Hours for this student (Weighted by session duration)
            student_map[reg]['total_hours'] += record.session.session_duration

            if record.status in ['Present', 'OD']:
                student_map[reg]['present_hours'] += record.session.session_duration

        # --- D. BUILD FINAL LISTS ---
        actual_student_count = len(student_map) 
        student_stats = []
        defaulters = []

        for reg, data in student_map.items():
            s = data['obj']
            attended = data['present_hours']
            
            # Use student's personal total hours (handles late joiners correctly)
            # If viewing single course, use global total. If aggregate, use personal.
            base = data['total_hours'] if not course_id else total_hours_taught
            
            pct = round((attended / base) * 100, 1) if base > 0 else 0.0
            severity_label = "Critical" if pct < 75 else "Safe"
            
            stat_obj = {
                'id': s.id,
                'name': s.name,
                'reg_no': s.reg_no,
                'present': attended, 
                'total': base,       
                'percent': pct,
                'severity': severity_label 
            }
            student_stats.append(stat_obj)
            
            if pct < 75:
                defaulters.append(stat_obj)

        # --- E. CHARTS DATA ---
        pie_data = []
        if course_id:
            # Subject View: Split by Status
            p = AttendanceRecord.objects.filter(session__in=sessions_qs, status='Present').count()
            od = AttendanceRecord.objects.filter(session__in=sessions_qs, status='OD').count()
            a = AttendanceRecord.objects.filter(session__in=sessions_qs, status='Absent').count()
            pie_data = [p, od, a]
        else:
            # Overall View: Safe vs Critical
            safe_count = actual_student_count - len(defaulters)
            pie_data = [safe_count, len(defaulters)]

        # Trend Data (Last 7 Days)
        trend_data = []
        trend_labels = []
        dates = sessions_qs.dates('date', 'day', order='DESC')[:7]
        dates = sorted(dates) # Chronological for chart
        
        for d in dates:
            daily_sess = sessions_qs.filter(date=d)
            # Count RAW records for that day across all subjects
            day_records = AttendanceRecord.objects.filter(session__in=daily_sess)
            
            if day_records.exists():
                present_count = day_records.filter(status__in=['Present', 'OD']).count()
                total_count = day_records.count()
                avg = round((present_count / total_count) * 100, 1)
                trend_data.append(avg)
                trend_labels.append(d.strftime("%d %b"))

        # History Data (Last 15 Sessions)
        history_data = []
        recent_sessions = sessions_qs.select_related('course').order_by('-date', '-start_session')[:15]
        for sess in recent_sessions:
            history_data.append({
                'date': sess.date.strftime("%Y-%m-%d"),
                'session': f"{sess.course.subject_code} (S{sess.start_session})",
                'present': AttendanceRecord.objects.filter(session=sess, status='Present').count(),
                'od': AttendanceRecord.objects.filter(session=sess, status='OD').count(),
                'absent': AttendanceRecord.objects.filter(session=sess, status='Absent').count(),
            })

        return JsonResponse({
            'meta': {
                'title': title, 
                'subtitle': subtitle, 
                'course_id': course_id,
                'faculty_name': faculty_name
            },
            'stats': {
                'total_students': actual_student_count,
                'total_sessions': total_sessions_count,
                'total_hours': total_hours_taught,
            },
            'charts': {
                'trend_labels': trend_labels,
                'trend_data': trend_data,
                'pie_data': pie_data 
            },
            'defaulters': defaulters,
            'leaderboard': sorted(student_stats, key=lambda x: x['percent'], reverse=True),
            'history': history_data
        })

    except Exception as e:
        import traceback
        print(traceback.format_exc())
        return JsonResponse({'error': str(e)}, status=500)

@csrf_exempt
def export_admin_course_report(request, course_id):
    """
    Admin: Generates a detailed session-wise CSV report for a specific course.
    FIX: Now includes Inactive (Deleted) students to preserve attendance history.
    """
    college_id = request.session.get('college_id')
    if not college_id:
        return HttpResponse("Unauthorized", status=401)

    try:
        # 1. Fetch Course & Sessions
        course = Course.objects.get(id=course_id)
        sessions = course.sessions.all().order_by('date', 'start_session')
        
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = f'attachment; filename="{course.subject_name}_{course.class_name}_Report.csv"'
        writer = csv.writer(response)
        
        # 2. Dynamic Headers
        # Format: S.No, Reg No, Name, Status, [Date (S1-S2)]..., Present, OD, Absent, %
        session_headers = [f"{s.date.strftime('%d-%m')} (S{s.start_session}-S{s.end_session})" for s in sessions]
        headers = ['S.No', 'Reg No', 'Name', 'Current Status'] + session_headers + ['Total Present', 'Total OD', 'Total Absent', 'Percentage']
        writer.writerow(headers)
        
        # 3. Fetch ALL Enrolled Students (Active + Inactive)
        # We remove .filter(is_active=True) to ensure deleted students appear in the audit trail
        students = course.enrolled_students.all().order_by('reg_no')
        
        # 4. Prefetch Attendance Records
        records_map = {
            (r.student_id, r.session_id): r.status 
            for r in AttendanceRecord.objects.filter(session__in=sessions)
        }
        
        # 5. Build Rows
        for idx, s in enumerate(students, 1):
            # Student Details
            active_status = "Active" if s.is_active else "Deleted/Inactive"
            row = [idx, s.reg_no, s.name, active_status]
            
            p_hours = 0
            od_hours = 0
            a_hours = 0
            total_possible = 0
            
            # Loop through every session in this course
            for sess in sessions:
                status = records_map.get((s.id, sess.id), '-')
                sess_dur = int(sess.session_duration) if sess.session_duration else 1
                
                # Update counters
                if status == 'Present':
                    p_hours += sess_dur
                elif status == 'OD':
                    od_hours += sess_dur
                elif status == 'Absent':
                    a_hours += sess_dur
                
                # Only count 'total' if the student was actually recorded (joined before this session)
                # OR if you want to penalize late joiners, just add sess_dur always.
                # Standard Logic: If record exists, count it. If not ('-'), implies not enrolled yet or holiday.
                if status != '-':
                    total_possible += sess_dur
                
                row.append(status)
            
            # Calculate Percentage
            pct = 0
            if total_possible > 0:
                pct = int(round(((p_hours + od_hours) / total_possible) * 100))
            
            row.extend([p_hours, od_hours, a_hours, f"{pct}%"])
            writer.writerow(row)
            
        return response

    except Course.DoesNotExist:
        return HttpResponse('Course not found', status=404)
    except Exception as e:
        logger.exception(f"Error generating course CSV: {str(e)}")
        return HttpResponse("Error generating report", status=500)

@csrf_exempt
def export_admin_class_overall_report(request, class_id):
    """
    Admin Master Report: Consolidated & Weighted.
    FIX 1: Groups by 'Subject Name' to merge duplicate/split batch columns.
    FIX 2: Calculates percentage based ONLY on courses the student is enrolled in (Fixes Elective % drop).
    """
    college_id = request.session.get('college_id')
    if not college_id: return HttpResponse("Unauthorized", status=401)

    try:
        ac_class = AcademicClass.objects.get(id=class_id)
        students = Student.objects.filter(academic_class=ac_class).order_by('reg_no')
        all_courses = Course.objects.filter(class_name=ac_class.class_name, is_active=True)

        # 1. GROUP COURSES BY SUBJECT NAME
        # This merges "Core Paper 1 (Batch A)" and "Core Paper 1 (Batch B)" into one column
        subject_map = {} # { 'Subject Name': [course_id_1, course_id_2], ... }
        
        # Also pre-calculate hours for each individual course ID
        course_hours_cache = {} 
        
        for c in all_courses:
            if c.subject_name not in subject_map:
                subject_map[c.subject_name] = []
            subject_map[c.subject_name].append(c.id)
            
            # Cache hours per course instance
            hours = int(AttendanceSession.objects.filter(course=c).aggregate(t=Sum('session_duration'))['t'] or 0)
            course_hours_cache[c.id] = hours

        sorted_subjects = sorted(subject_map.keys())

        # 2. Map Enrollments
        enrollment_set = set(
            Course.enrolled_students.through.objects.filter(
                course__in=all_courses,
                student__in=students
            ).values_list('student_id', 'course_id')
        )

        # 3. Generate CSV
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = f'attachment; filename="{ac_class.class_name}_Master_Report.csv"'
        writer = csv.writer(response)
        
        headers = ['S.No', 'Reg No', 'Name'] + sorted_subjects + ['OVERALL %']
        writer.writerow(headers)
        
        for idx, s in enumerate(students, 1):
            row = [idx, s.reg_no, s.name]
            
            student_total_attended = 0
            student_total_possible = 0
            
            for sub_name in sorted_subjects:
                course_ids = subject_map[sub_name]
                
                # A. Find which specific instance the student is enrolled in
                enrolled_course_id = None
                for cid in course_ids:
                    if (s.id, cid) in enrollment_set:
                        enrolled_course_id = cid
                        break # Student can only be in one batch per subject usually
                
                if not enrolled_course_id:
                    row.append("") # Not enrolled in this subject
                    continue

                # B. Get stats ONLY for that specific enrolled course
                possible = course_hours_cache.get(enrolled_course_id, 0)
                
                if possible > 0:
                    attended = int(AttendanceRecord.objects.filter(
                        student=s,
                        session_id__course_id=enrolled_course_id,
                        status__in=['Present', 'OD']
                    ).aggregate(h=Sum('session__session_duration'))['h'] or 0)
                    
                    pct = int(round((attended / possible) * 100))
                    row.append(f"{pct}%")
                    
                    # Accumulate for Overall Average
                    student_total_attended += attended
                    student_total_possible += possible
                else:
                    row.append("0%")

            # C. Weighted Overall Calculation
            if student_total_possible > 0:
                overall_pct = int(round((student_total_attended / student_total_possible) * 100))
                row.append(f"{overall_pct}%")
            else:
                row.append("0%")
            
            writer.writerow(row)
            
        return response

    except Exception as e:
        logger.exception(f"Report Error: {str(e)}")
        return HttpResponse(str(e), status=500)

@csrf_exempt
def export_deleted_students_csv(request, class_id):
    """Admin CSV: export attendance for students marked inactive (deleted) in a class."""
    try:
        academic_class = AcademicClass.objects.get(id=class_id)
        # Get deleted students
        students = Student.objects.filter(academic_class=academic_class, is_active=False).order_by('reg_no')
        # All courses for this class (columns)
        courses = Course.objects.filter(class_name=academic_class.class_name).order_by('subject_name')

        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = f'attachment; filename="deleted_students_{academic_class.class_name}.csv"'
        writer = csv.writer(response)

        # Header: S.No, RegNo, Name, Email, JoinedAt, [per-course columns...], Overall%
        course_headers = [f"{c.subject_name} (%)" for c in courses]
        writer.writerow(['S.No', 'Reg No', 'Name', 'Email', 'JoinedAt'] + course_headers + ['Overall %'])

        for idx, student in enumerate(students, 1):
            row = [idx, student.reg_no, student.name, student.email or '', student.joined_at.strftime('%Y-%m-%d') if student.joined_at else '']
            overall_present = 0
            overall_total = 0
            for c in courses:
                total_hours = AttendanceSession.objects.filter(course=c).aggregate(t=Sum('session_duration'))['t'] or 0
                # Prefer filtering by student object to avoid reg_no duplication/mismatch issues
                attended = AttendanceRecord.objects.filter(student=student, session__course=c, status__in=['Present', 'OD']).aggregate(h=Sum('session__session_duration'))['h'] or 0
                pct = round((attended / total_hours) * 100, 1) if total_hours > 0 else 0.0
                row.append(f"{pct}%")
                overall_present += attended
                overall_total += total_hours

            overall_pct = round((overall_present / overall_total) * 100, 1) if overall_total > 0 else 0.0
            row.append(f"{overall_pct}%")
            writer.writerow(row)

        return response
    except AcademicClass.DoesNotExist:
        return HttpResponse('Class not found', status=404)
    except Exception as e:
        logger.exception(f"Error exporting deleted students CSV for class {class_id}: {e}")
        return HttpResponse("Error generating deleted students report", status=500)

@csrf_exempt
def get_class_report_card_api(request):
    """
    Returns student report card WITH consecutive absence streak.
    Streak = Number of consecutive DAYS (working backwards from today) 
    where the student was Absent for ALL sessions on that day.
    """
    class_id = request.GET.get('class_id')
    if not class_id:
        return JsonResponse({'error': 'Class ID required'}, status=400)

    try:
        ac_class = AcademicClass.objects.get(id=class_id)
        
        # 1. Master List
        admin_students = Student.objects.filter(academic_class=ac_class, is_active=True).order_by('reg_no')
        target_reg_nos = [s.reg_no for s in admin_students]

        # 2. Get Sessions & Dates (Ordered Latest First)
        courses = Course.objects.filter(class_name=ac_class.class_name)
        sessions = AttendanceSession.objects.filter(course__in=courses).order_by('-date')
        
        # Get unique dates for streak calculation
        unique_dates = list(sessions.values_list('date', flat=True).distinct())
        unique_dates.sort(reverse=True) # Ensure latest date is first

        # 3. Fetch Records with Date Info
        records = AttendanceRecord.objects.filter(
            session__in=sessions,
            student__reg_no__in=target_reg_nos
        ).values('student__reg_no', 'status', 'session__session_duration', 'session__date')

        # 4. Process Data in Memory
        stats_map = {}
        attendance_history = {} # Format: {reg_no: {date: [status, status, ...]}}

        for r in records:
            reg = r['student__reg_no']
            status = r['status']
            duration = r['session__session_duration'] or 1
            date_str = r['session__date'].strftime('%Y-%m-%d')

            # Aggregate Totals
            if reg not in stats_map:
                stats_map[reg] = {'P': 0, 'OD': 0, 'A': 0}
            
            if status == 'Present': stats_map[reg]['P'] += duration
            elif status == 'OD': stats_map[reg]['OD'] += duration
            elif status == 'Absent': stats_map[reg]['A'] += duration

            # Build History for Streak Calc
            if reg not in attendance_history:
                attendance_history[reg] = {}
            if date_str not in attendance_history[reg]:
                attendance_history[reg][date_str] = []
            
            attendance_history[reg][date_str].append(status)

        # 5. Build Response
        data = []
        seen_regs = set()

        for s in admin_students:
            if s.reg_no in seen_regs: continue
            seen_regs.add(s.reg_no)

            # --- CALCULATE STREAK ---
            streak_days = 0
            student_dates = attendance_history.get(s.reg_no, {})
            
            for d_obj in unique_dates:
                d_str = d_obj.strftime('%Y-%m-%d')
                day_statuses = student_dates.get(d_str, [])
                
                if not day_statuses:
                    continue # Skip days where student had no class scheduled (optional logic)
                
                # Check if ALL sessions on this day were Absent
                is_full_absent = all(st == 'Absent' for st in day_statuses)
                
                if is_full_absent:
                    streak_days += 1
                else:
                    break # Streak broken (Present or OD found)
            # ------------------------

            stat = stats_map.get(s.reg_no, {'P': 0, 'OD': 0, 'A': 0})
            student_total = stat['P'] + stat['OD'] + stat['A']
            pct = round(((stat['P'] + stat['OD']) / student_total) * 100, 1) if student_total > 0 else 0

            data.append({
                'id': s.id,
                'reg_no': s.reg_no,
                'name': s.name,
                'present': stat['P'],
                'od': stat['OD'],
                'absent': stat['A'],
                'total': student_total,
                'percentage': pct,
                'consecutive_days': streak_days # <--- Sending this to Frontend
            })

        data.sort(key=lambda x: x['reg_no'])
        return JsonResponse({'students': data})

    except Exception as e:
        logger.exception(f"Report Error: {e}")
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
    
    if not context or str(user_otp) != str(context['otp']) or context['action'] != 'archive_class':
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

@csrf_exempt
def get_class_history_api(request):
    class_id = request.GET.get('class_id')
    try:
        ac_class = AcademicClass.objects.get(id=class_id)
        
        # Fetch only Inactive (Archived) courses
        history_courses = Course.objects.filter(
            class_name=ac_class.class_name, 
            is_active=False
        ).order_by('-semester', 'subject_name')
        
        data = []
        for c in history_courses:
            # Calculate final attendance summary for that course
            total_sessions = AttendanceSession.objects.filter(course=c).count()
            fac_name = c.faculty.name if c.faculty else "Unassigned"
            ended_date = "N/A"
            if hasattr(c, 'created_at') and c.created_at:
                ended_date = c.created_at.strftime("%Y-%m-%d")
            
            data.append({
                'id': c.id,
                'semester': c.semester,
                'subject': c.subject_name,
                'code': c.subject_code,
                'faculty': fac_name,
                'total_sessions': total_sessions,
                'ended_date': c.created_at.strftime("%Y-%m-%d") # Or use a modified_at field
            })
            
        return JsonResponse({'history': data})
    except AcademicClass.DoesNotExist:
        return JsonResponse({'error': 'Class not found'}, status=404)
    except Exception as e:
        print(f"History API Error: {str(e)}")
        return JsonResponse({'error': str(e)}, status=500)

@csrf_exempt
def get_alumni_records_api(request):
    """Fetch archived attendance for a specific batch/sem"""
    dept_id = request.GET.get('dept_id')
    batch = request.GET.get('batch') # e.g. "2020-2024"
    
    # 1. Find Inactive Classes for this batch
    classes = AcademicClass.objects.filter(
        department_id=dept_id, 
        academic_year=batch,
        is_active=False
    )
    
    data = []
    for cls in classes:
        # Get final stats for this class
        students = Student.objects.filter(academic_class=cls).count()
        courses_count = Course.objects.filter(class_name=cls.class_name, is_active=False).count()
        
        data.append({
            'class_id': cls.id,
            'name': cls.class_name,
            'section': cls.section,
            'students': students,
            'courses_held': courses_count
        })
        
    return JsonResponse({'records': data})

@csrf_exempt
def get_deleted_students_api(request):
    """Return JSON list of deleted (inactive) students for a given class_id (query param)."""
    try:
        class_id = request.GET.get('class_id')
        if not class_id:
            return JsonResponse({'error': 'class_id required'}, status=400)

        academic_class = AcademicClass.objects.get(id=class_id)
        students = Student.objects.filter(academic_class=academic_class, is_active=False).order_by('reg_no')
        courses = Course.objects.filter(class_name=academic_class.class_name).order_by('subject_name')

        out = []
        for s in students:
            overall_present = 0
            overall_total = 0
            per_course = []
            for c in courses:
                total_hours = AttendanceSession.objects.filter(course=c).aggregate(t=Sum('session_duration'))['t'] or 0
                present_hours = AttendanceRecord.objects.filter(student=s, session__course=c, status='Present').aggregate(h=Sum('session__session_duration'))['h'] or 0
                od_hours = AttendanceRecord.objects.filter(student=s, session__course=c, status='OD').aggregate(h=Sum('session__session_duration'))['h'] or 0
                absent_hours = AttendanceRecord.objects.filter(student=s, session__course=c, status='Absent').aggregate(h=Sum('session__session_duration'))['h'] or 0
                attended = present_hours + od_hours
                pct = round((attended / total_hours) * 100, 1) if total_hours > 0 else 0.0
                per_course.append({'course_id': c.id, 'subject': c.subject_name, 'code': c.subject_code, 'present_hours': present_hours, 'od_hours': od_hours, 'absent_hours': absent_hours, 'total_hours': total_hours, 'percentage': pct})
                overall_present += attended
                overall_total += total_hours

            overall_pct = round((overall_present / overall_total) * 100, 1) if overall_total > 0 else 0.0

            # last record snapshot
            last = AttendanceRecord.objects.filter(student=s).select_related('session').order_by('-session__date').first()
            last_snapshot = None
            if last:
                last_snapshot = {
                    'date': last.session.date.strftime('%Y-%m-%d') if last.session and last.session.date else None,
                    'status': last.status,
                    'duration': last.session.session_duration if last.session else None
                }

            out.append({
                'id': s.id, 'reg_no': s.reg_no, 'name': s.name, 'email': s.email or '', 'joined_at': s.joined_at.strftime('%Y-%m-%d') if s.joined_at else None,
                'overall_pct': overall_pct, 'per_course': per_course, 'last_snapshot': last_snapshot
            })

        return JsonResponse({'students': out})
    except AcademicClass.DoesNotExist:
        return JsonResponse({'error': 'Class not found'}, status=404)
    except Exception as e:
        logger.exception(f"Error fetching deleted students for class {request.GET.get('class_id')}: {e}")
        return JsonResponse({'error': str(e)}, status=500)
