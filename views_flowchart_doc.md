# Views Functions Flowchart Documentation

## Table of Contents
1. [Auth Views](#auth-views)
2. [College Auth](#college-auth)
3. [College Core](#college-core)
4. [College Faculty](#college-faculty)
5. [Course Views](#course-views)
6. [Faculty Views](#faculty-views)
7. [Report Views](#report-views)
8. [Semester Views](#semester-views)
9. [Student Views](#student-views)
10. [Timetable Views](#timetable-views)
11. [Utility Functions](#utility-functions)

---

## Auth Views

### 1. index_view()
```
START
  ├─ Count Colleges, Departments, Faculty, Students
  ├─ Format numbers with K/M notation (1200 → 1.2K)
  ├─ Create context with formatted + raw counts
  └─ Render index.html with context
END
```

### 2. login()
```
START (POST Request)
  ├─ Rate Limit Check (5 attempts/15 min)
  ├─ Validate email format
  ├─ Validate password not empty
  ├─ Query Faculty by college_email
  │  ├─ Faculty Found?
  │  │  ├─ YES: Check password hash
  │  │  │  ├─ Correct?
  │  │  │  │  ├─ YES: Check if verified
  │  │  │  │  │  ├─ YES: Clear session, set new session data → SUCCESS
  │  │  │  │  │  └─ NO: NOT_VERIFIED
  │  │  │  │  └─ NO: INVALID
  │  │  └─ NO: Faculty DoesNotExist → INVALID
  └─ CATCH exceptions → INVALID
GET: Render login.html
END
```

### 3. send_otp()
```
START (POST Request)
  ├─ Rate Limit Check (3 attempts/10 min)
  ├─ Validate email format
  ├─ Check request type (College Admin or Faculty)
  ├─ Faculty Flow: Check if email already exists
  │  └─ YES: EMAIL_EXISTS error
  ├─ Generate random 6-digit OTP
  ├─ Send email with OTP
  │  ├─ Success: Continue
  │  └─ Fail: EMAIL_ERROR
  ├─ Clear existing OTP session data
  ├─ Store in session: pending_email, pending_otp, otp_timestamp
  └─ OTP_SENT
END
```

### 4. verify_email_otp()
```
START (POST Request)
  ├─ Validate email format
  ├─ Validate OTP (6 digits)
  ├─ Check OTP expiration (10 minutes)
  │  ├─ Expired: Clear session, EXPIRED
  │  └─ Valid: Continue
  ├─ Compare OTP with session OTP
  │  ├─ Match?
  │  │  ├─ YES: Set email_verified=True, email_verified_time
  │  │  │       Return VERIFIED
  │  │  └─ NO: WRONG
  └─ CATCH exceptions → INVALID
END
```

### 5. register()
```
START (POST Request)
  ├─ Check email_verified flag
  │  └─ NOT verified: OTP_NOT_VERIFIED
  ├─ Check email_verified_time (within 30 min)
  │  └─ Expired: OTP_EXPIRED
  ├─ Validate all inputs (name, college, dept, designation, mobile, password)
  ├─ Clean mobile number (remove non-digits)
  ├─ Validate mobile length (10-15 digits)
  ├─ Check if email still pending (not taken by someone else)
  ├─ Generate unique faculty_reg_id
  ├─ Create NewFaculty record
  │  ├─ IntegrityError: Retry with new unique_id
  ├─ Clear session data
  └─ REGISTERED
END
```

### 6. forgot_send_otp()
```
START (POST Request)
  ├─ Validate email
  ├─ Query Faculty by college_email
  │  └─ NOT found: NO_EMAIL
  ├─ Generate OTP
  ├─ Check rate limit from cache
  │  ├─ Rate limit exceeded: OTP_RATE_LIMIT_EXCEEDED
  ├─ Store OTP in cache (10 min expiry)
  ├─ Store OTP timestamp in cache
  ├─ Increment attempt counter in cache
  ├─ Send email with OTP
  └─ FP_OTP_SENT
END
```

### 7. forgot_verify_otp()
```
START (POST Request)
  ├─ Get email and OTP from request
  ├─ Fetch OTP from cache
  │  ├─ NOT found: FP_OTP_EXPIRED
  ├─ Check timestamp (within 10 min)
  │  ├─ Expired: Delete cache entries → FP_OTP_EXPIRED
  ├─ Compare OTP with constant-time comparison
  │  ├─ Match?
  │  │  ├─ YES: Set fp_verified=True, delete cache entries
  │  │  │       Return FP_VERIFIED
  │  │  └─ NO: FP_WRONG
  └─ END
END
```

### 8. reset_password()
```
START (POST Request)
  ├─ Check fp_verified flag
  │  └─ NOT verified: NOT_ALLOWED
  ├─ Get email from session
  ├─ Query Faculty by email
  ├─ Hash new password
  ├─ Update Faculty.password
  ├─ Save
  └─ PASSWORD_RESET
END
```

### 9. logout_view()
```
START
  ├─ request.session.flush() [Clear all session data]
  └─ Redirect to login page
END
```

### 10. jwt_login_api()
```
START (@csrf_exempt, POST)
  ├─ Rate Limit Check (5 attempts/15 min)
  ├─ Parse JSON request body
  ├─ Validate email format
  ├─ Validate password not empty
  ├─ Try Faculty login
  │  ├─ Faculty found?
  │  │  ├─ YES: Check password
  │  │  │  ├─ YES: Check is_verified
  │  │  │  │  ├─ YES: user_type='faculty'
  │  │  │  │  └─ NO: Error
  │  │  │  └─ NO: Error
  │  │  └─ NO: Try College login
  │  └─ College found?
  │     ├─ YES: Check password → user_type='college_admin'
  │     └─ NO: Error
  ├─ Create access_token and refresh_token
  └─ Return JSON with tokens
END
```

### 11. jwt_refresh_api()
```
START (@csrf_exempt, POST)
  ├─ Parse JSON request body
  ├─ Get refresh_token from request
  │  └─ NOT present: Error
  ├─ Verify refresh_token and create new access_token
  │  ├─ Valid?
  │  │  ├─ YES: Return new access_token
  │  │  └─ NO: Error (Invalid or expired)
  └─ END
END
```

---

## College Auth

### 12. college_login_view()
```
START (GET)
  └─ Render college_login.html
END
```

### 13. college_register_api()
```
START (@rate_limit, POST, JSON)
  ├─ Check email_verified flag
  │  └─ NOT verified: Unauthorized
  ├─ Check email_verified_time (within 30 min)
  ├─ Validate email format
  ├─ Validate college code (4-10 alphanumeric)
  ├─ Verify email matches session email
  ├─ Validate college name
  ├─ Validate website URL (if provided)
  ├─ Block public email providers
  ├─ Check if college_code exists
  │  └─ YES: Error
  ├─ Check if admin_email exists
  │  └─ YES: Error
  ├─ Create College record
  ├─ Clear session data
  └─ Return success
END
```

### 14. college_login_api()
```
START (@rate_limit, POST)
  ├─ Validate email format
  ├─ Validate password not empty
  ├─ Query College by admin_email
  ├─ Check password hash
  │  ├─ Match?
  │  │  ├─ YES: Set session (college_id, user_type='college_admin')
  │  │  │       Return LOGIN_SUCCESS
  │  │  └─ NO: Invalid credentials
  └─ END
END
```

### 15. college_forgot_otp()
```
START (POST, @rate_limit)
  ├─ Get email from request
  ├─ Query College by admin_email
  │  └─ NOT found: Return 404
  ├─ Generate OTP
  ├─ Save to session (college_fp_email, college_fp_otp, college_fp_verified=False)
  ├─ Send email with OTP
  └─ Return OTP_SENT
END
```

### 16. college_forgot_verify()
```
START (POST)
  ├─ Get email and OTP from request
  ├─ Compare with session data
  │  ├─ Match?
  │  │  ├─ YES: Set college_fp_verified=True → VERIFIED
  │  │  └─ NO: INVALID
  └─ END
END
```

### 17. college_reset_pass()
```
START (POST)
  ├─ Check college_fp_verified
  │  └─ NOT verified: Unauthorized
  ├─ Get new password and email from session
  ├─ Query College by admin_email
  ├─ Hash password
  ├─ Update and save
  ├─ Clear session keys
  └─ SUCCESS
END
```

### 18. college_logout_view()
```
START
  ├─ request.session.flush()
  └─ Redirect to college_login
END
```

---

## College Core

### 19. college_dashboard_view()
```
START (GET)
  ├─ Get college_id from session
  │  └─ NOT present: Redirect to college_login
  ├─ Get College object
  │  └─ NOT found: 404
  ├─ Render college_dashboard.html with college context
  └─ END
```

### 20. get_college_dashboard_data()
```
START (@csrf_exempt, GET)
  ├─ Get college_id from session or JWT
  │  └─ NOT present: Redirect to college_login
  ├─ Check cache (college_dashboard:{college_id})
  │  ├─ Found: Return cached data
  ├─ Fetch College object
  ├─ Prefetch departments with classes and faculty_members
  ├─ For each department:
  │  ├─ Get all academic classes
  │  ├─ Build classes_list with metadata
  │  └─ Count faculty members
  ├─ Fetch all verified Faculty for this college
  ├─ Build faculty_list with details
  ├─ Aggregate stats
  ├─ Cache response (10 min)
  └─ Return JSON with departments and faculty
END
```

### 21. add_department_api()
```
START (POST)
  ├─ Check OTP verification (add_dept_verified)
  │  └─ NOT verified: Unauthorized
  ├─ Get college_id, name, year from request
  ├─ Check if department with same name exists
  │  └─ YES: Error
  ├─ Create Department
  ├─ Invalidate college dashboard cache
  ├─ Reset verification
  └─ Return success
END
```

### 22. add_academic_class_api()
```
START (@csrf_exempt, @transaction.atomic, POST, JSON)
  ├─ Parse JSON (dept_id, name, section, batch, students, currentYear)
  ├─ Get college object from session
  ├─ Check if class + section + batch exists
  │  └─ YES: Error
  ├─ Validate students (check for duplicate reg_nos in college)
  │  └─ Found duplicates: Error with list
  ├─ Create AcademicClass
  ├─ For each student:
  │  └─ Create Student linked to college and class
  ├─ Bulk create students
  ├─ Invalidate cache
  └─ Return success
END
```

### 23. search_faculty_api()
```
START (GET, @csrf_exempt)
  ├─ Get query string 'q'
  ├─ Filter NewFaculty by college_email (case-insensitive)
  ├─ Limit to 5 results
  └─ Return JSON with [id, name, email]
END
```

### 24. get_college_notifications_api()
```
START (GET)
  ├─ Get college_id from session
  │  └─ NOT present: Unauthorized
  ├─ Query CollegeNotification (is_read=False, for this college)
  ├─ Order by created_at (newest first)
  ├─ Format each notification
  └─ Return JSON with notifications
END
```

### 25. mark_notification_read_api()
```
START (@csrf_exempt, POST, JSON)
  ├─ Get notification id
  ├─ Update is_read=True
  └─ Return JSON
END
```

### 26. get_class_students_api()
```
START (@csrf_exempt, GET)
  ├─ Get class_id from request
  ├─ Query AcademicClass
  ├─ Get active students for this class
  ├─ Return JSON with:
  │  ├─ className, batch, dept_id
  │  ├─ semester_start/end dates
  │  └─ students list
  └─ END
END
```

### 27. get_class_students_admin_all()
```
START (@csrf_exempt, GET)
  ├─ Get class_id from request
  ├─ Query AcademicClass
  ├─ Get ALL students (active + inactive) for this class
  ├─ Return JSON with class name and students
  └─ END
END
```

### 28. add_student_to_existing_class_api()
```
START (@csrf_exempt, POST, JSON)
  ├─ Get class_id, reg_no, name, email
  ├─ Get college_id from session
  ├─ Check if student with reg_no exists in college
  │  └─ YES: Error
  ├─ Create Student
  ├─ Try to sync student into related Course rosters
  │  └─ (If sync fails, continue anyway)
  └─ Return success
END
```

### 29. delete_student_api()
```
START (@csrf_exempt, @transaction.atomic, POST, JSON)
  ├─ Get student_id
  ├─ Query Student
  │  └─ NOT found: 404
  ├─ Soft delete (is_active=False)
  ├─ Find active courses containing this student
  ├─ For each course:
  │  └─ Get faculty and send notification
  │  └─ Invalidate faculty dashboard cache
  └─ Return success
END
```

### 30. get_admin_student_profile()
```
START (GET, parameter: student_id)
  ├─ Get student_id
  ├─ Query Student
  ├─ Check if student has academic_class
  ├─ Get all enrolled courses (active)
  ├─ For each course:
  │  ├─ Get total hours for course
  │  ├─ Get student's present/od/absent hours
  │  ├─ Calculate percentage
  │  └─ Append to per_course list
  ├─ Calculate overall stats:
  │  ├─ Total hours, sessions, attendance %
  │  ├─ Safe skip logic (75% threshold)
  │  └─ Determine status (Safe Zone or Critical)
  └─ Return JSON with student profile + stats
END
```

---

## College Faculty

### 31. search_faculty_api() [College Faculty Version]
```
START (GET, @csrf_exempt)
  ├─ Get query string
  ├─ Filter NewFaculty by college_email
  └─ Return results
END
```

### 32. search_faculty_by_id_api()
```
START (GET, @csrf_exempt)
  ├─ Get reg_id from query
  ├─ Query NewFaculty by faculty_reg_id
  │  ├─ Found: Return {found: true, id, name, email}
  │  └─ NOT found: Return {found: false}
  └─ END
END
```

### 33. assign_faculty_api()
```
START (POST)
  ├─ Get faculty_id and dept_id
  ├─ Query NewFaculty
  ├─ Update department_link_id
  ├─ Save
  └─ Return success
END
```

### 34. send_faculty_invite_api()
```
START (@csrf_exempt, POST, JSON)
  ├─ Get college_id from session
  │  └─ NOT present: Unauthorized
  ├─ Get faculty_db_id and dept_id
  ├─ Query faculty
  ├─ Check if faculty already linked to a college
  │  ├─ YES: Error (cannot invite, must leave first)
  ├─ Check for existing Pending/Approved requests
  │  ├─ YES: Error
  ├─ Create FacultyJoinRequest
  ├─ Create FacultyNotification
  └─ Return success
END
```

### 35. get_faculty_details_admin()
```
START (GET, @csrf_exempt)
  ├─ Get faculty_id
  ├─ Query NewFaculty
  ├─ Get courses for this faculty
  ├─ Build course_data with:
  │  ├─ title: subject_name (class_name)
  │  └─ is_official: is_assigned boolean
  └─ Return JSON with faculty details and courses
END
```

### 36. terminate_faculty_api()
```
START (@csrf_exempt, @transaction.atomic, POST, JSON)
  ├─ Get faculty_id and replacement_id (optional)
  ├─ Query faculty
  ├─ Delete old FacultyJoinRequests
  ├─ Create termination notification (email + dashboard)
  ├─ Get faculty's courses
  │  ├─ If replacement_id provided:
  │  │  ├─ Unassign courses (faculty=None)
  │  │  ├─ For each course:
  │  │  │  └─ Create ClassAssignmentRequest for replacement
  │  │  └─ Notify new faculty
  │  └─ Else: Orphan courses (faculty=None, is_assigned=False)
  ├─ Unlink faculty from department
  ├─ Clear college name
  └─ Return success message
END
```

---

## Course Views

### 37. add_dept_course_api()
```
START (POST)
  ├─ Get dept_id, course_code, course_title, semester, course_type
  ├─ Validate all required fields
  ├─ Check if course_code exists in department
  │  └─ YES: Error
  ├─ Create DepartmentCourse
  └─ Return success
END
```

### 38. get_dept_courses_api()
```
START (@csrf_exempt, GET)
  ├─ Get dept_id
  ├─ Query DepartmentCourse
  ├─ For each course:
  │  ├─ If Elective: sort_key = 999, semester = "Elective"
  │  └─ Else: sort_key = semester number
  ├─ Sort by sort_key and title
  └─ Return JSON with courses
END
```

### 39. delete_dept_course_api()
```
START (@csrf_exempt, POST)
  ├─ Get course_id
  ├─ Query DepartmentCourse
  │  └─ NOT found: 404
  ├─ Delete
  └─ Return success
END
```

### 40. edit_dept_course_api()
```
START (@csrf_exempt, POST)
  ├─ Get course_id
  ├─ Query DepartmentCourse
  ├─ Update course_name, course_code, semester, course_type
  ├─ Save
  └─ Return success
END
```

### 41. assign_subject_to_class_api()
```
START (@csrf_exempt, POST, JSON)
  ├─ Get class_id, subject_id, faculty_id, total_hours, college_id (from session)
  ├─ Query subject and class objects
  ├─ Check if faculty already teaching this exact class
  │  └─ YES: Error
  ├─ Check if another faculty is teaching it (conflict)
  │  └─ YES: Error with faculty name
  ├─ Check existing ClassAssignmentRequest
  │  ├─ Approved: Error (must revoke first)
  │  └─ Pending: Error (already pending)
  ├─ Check if reassignment (course exists with no faculty)
  ├─ Create ClassAssignmentRequest
  ├─ Create FacultyNotification
  └─ Return success
END
```

### 42. revoke_course_api()
```
START (POST)
  ├─ Get course_id and college_id
  ├─ Query Course (verify college ownership)
  ├─ Find related ClassAssignmentRequest (status='Approved')
  ├─ Update requests to 'Revoked'
  ├─ Create notification to faculty
  ├─ Set course.faculty=None
  ├─ Save
  └─ Return success
END
```

### 43. get_class_assigned_courses_api()
```
START (@csrf_exempt, GET)
  ├─ Get class_id
  ├─ Query AcademicClass
  ├─ Get active courses for this class
  ├─ For each course:
  │  ├─ Get faculty name (or "Unassigned")
  │  ├─ Count active enrolled students
  │  └─ Build course data
  └─ Return JSON with courses
END
```

### 44. assign_special_course_api()
```
START (@csrf_exempt, @transaction.atomic, POST, JSON)
  ├─ Get parent_class_id, subject_id, faculty_id, student_ids, batch_name
  ├─ Validate student_ids not empty
  ├─ Query subject, faculty, class
  ├─ Check if pending request exists for this exact setup
  │  └─ YES: Error
  ├─ Create ClassAssignmentRequest (store student_list_json)
  ├─ Create FacultyNotification
  ├─ Invalidate caches
  └─ Return success
END
```

### 45. get_dept_students_for_selection_api()
```
START (@csrf_exempt, GET)
  ├─ Get dept_id
  ├─ Query AcademicClass in department
  ├─ For each class:
  │  ├─ Get active students
  │  └─ Build class_name with section and year info
  └─ Return JSON with classes and students
END
```

### 46. get_class_assigned_courses_for_export_api()
```
START (@csrf_exempt, GET)
  ├─ Get college_id from session
  ├─ Get class_id from request
  ├─ Query AcademicClass
  ├─ Get ALL courses (active + inactive) for this class
  ├─ For each course:
  │  └─ Build course info with faculty name
  └─ Return JSON with courses
END
```

---

## Faculty Views

### 47. dashboard_template()
```
START (GET, @ensure_csrf_cookie, @never_cache)
  ├─ Get faculty_id from session
  │  └─ NOT present: Redirect to login
  ├─ Query NewFaculty
  ├─ Render dashboard.html with faculty context
  └─ END
```

### 48. get_dashboard_data()
```
START (@csrf_exempt, GET)
  ├─ Get faculty_id from session or JWT
  │  └─ NOT present: Unauthorized
  ├─ Check cache (faculty_dashboard:{faculty_id}, 5 min)
  │  ├─ Found: Return cached
  ├─ Query NewFaculty
  ├─ Get profile_photo URL
  ├─ Get all active courses (prefetch sessions, records, students)
  ├─ For each course:
  │  ├─ Get enrolled students
  │  ├─ Calculate total hours taught
  │  ├─ Calculate attendance percentage (weighted by hours)
  │  ├─ Build attendance_records (timeline)
  │  └─ Track global stats
  ├─ Calculate cumulative analytics
  ├─ Build response with classes and cumulative data
  ├─ Cache response (5 min)
  └─ Return JSON
END
```

### 49. create_class_api()
```
START (@csrf_exempt, @transaction.atomic, POST, JSON)
  ├─ Get faculty_id from session
  │  └─ NOT present: Unauthorized
  ├─ Parse JSON (className, subjectName, subjectCode, totalHours, students)
  ├─ Query NewFaculty
  ├─ Create personal Course (is_personal=True, is_assigned=False, is_active=True)
  ├─ For each student:
  │  ├─ Clean reg_no (strip, uppercase)
  │  ├─ Use get_or_create with STRICT criteria:
  │  │  ├─ reg_no (unique key)
  │  │  ├─ created_by_faculty=faculty (PRIVATE to this faculty)
  │  │  ├─ college=None (STRICTLY NOT linked to college)
  │  │  └─ Defaults: name, email, student_type='Personal', academic_class=None
  │  ├─ If NOT created (exists):
  │  │  ├─ Allow rename if faculty updates name
  │  │  └─ Save updated name
  │  └─ Add to students_to_add list
  ├─ Link all students to course via M2M (enrolled_students.set())
  ├─ Create optional college notification (if faculty linked to college)
  ├─ Invalidate faculty dashboard cache
  └─ Return success with course ID
END

CRITICAL FIX: Collision Prevention
- Each faculty has their own private student namespace (created_by_faculty=faculty)
- Multiple faculties can have "John (Reg: 101)" - they are isolated by faculty
- No unique constraint violation because lookup is scoped to (reg_no, created_by_faculty, college=None)
```

### 50. save_attendance_api()
```
START (@csrf_exempt, @transaction.atomic, POST, JSON)
  ├─ Get classId, date, records, startSession, endSession
  ├─ Validate session periods
  ├─ Lock course row (select_for_update)
  ├─ Check for conflicts (student already marked present in another course)
  │  └─ Found: Error with details
  ├─ Create AttendanceSession
  ├─ Bulk prepare attendance records
  ├─ Map student reg_no to ID (1 DB query)
  ├─ Count present/absent
  ├─ Bulk insert records (1 query)
  ├─ Update session counts
  ├─ Invalidate cache
  └─ Return success
END
```

### 51. edit_student_api()
```
START (@csrf_exempt, @transaction.atomic, POST, JSON)
  ├─ Get student_id
  ├─ Query Student
  │  └─ NOT found: 404
  ├─ Update name, reg_no, email
  ├─ Save
  ├─ Try to notify college (if applicable)
  │  └─ (Wrapped in try/except, non-critical)
  └─ Return success with updated student
END
```

### 52. delete_class_api()
```
START (DELETE, parameter: course_id)
  ├─ Get faculty_id from session
  ├─ Query Course (verify ownership)
  ├─ Check for linked ClassAssignmentRequest (status='Approved')
  │  ├─ Found:
  │  │  ├─ Update to 'Terminated'
  │  │  └─ Create admin notification
  │  └─ NOT found: No notification
  ├─ Delete Course
  ├─ Invalidate cache
  └─ Return message
END
```

### 53. edit_profile_api()
```
START (POST)
  ├─ Get faculty_id from session
  ├─ Query NewFaculty
  ├─ Update name, college_name, designation, department, mobile_num
  ├─ If profile_photo in FILES:
  │  └─ Update profile_photo
  ├─ Save
  └─ Return success with photo URL
END
```

---

## Report Views

### 54. export_attendance_csv()
```
START (GET, parameter: course_id)
  ├─ Get faculty_id from session
  │  └─ NOT present: Unauthorized
  ├─ Query Course
  │  └─ NOT found: 404
  ├─ Get all sessions ordered by date
  ├─ Create CSV response
  ├─ Write headers (S.No, Reg No, Name, Date/Session columns, Total Present/OD/Absent, %)
  ├─ Get active enrolled students
  ├─ Build attendance records map
  ├─ For each student:
  │  ├─ For each session:
  │  │  ├─ Get status from map
  │  │  └─ Accumulate hours
  │  ├─ Calculate percentage
  │  └─ Write row
  └─ Return CSV file
END
```

### 55. get_class_analytics_api() [Current Implementation]
```
START (@csrf_exempt, GET)
  ├─ Parse query parameters: class_id OR course_id
  │
  ├─ === SECTION A: CONTEXT SETUP ===
  ├─ If course_id (SUBJECT VIEW - Faculty Mode):
  │  ├─ Query Course by id
  │  ├─ Set title = subject_name
  │  ├─ Set subtitle = class_name
  │  ├─ Set faculty_name from course.faculty (or "Unassigned")
  │  ├─ Query sessions: AttendanceSession.filter(course=target_course)
  │  └─ Query students: course.enrolled_students.all()
  ├─ Else (OVERALL CLASS VIEW - Admin Mode):
  │  ├─ Query AcademicClass by id
  │  ├─ Set title = class_name
  │  ├─ Set subtitle = "Overall Performance"
  │  ├─ Set faculty_name = "Class Aggregate"
  │  ├─ Query sessions (ONLY official courses):
  │  │  ├─ Filter: course.academic_class=target_class
  │  │  ├─ Filter: course.is_personal=False
  │  │  └─ Order by date
  │  └─ Query students: active students in academic_class
  │
  ├─ === SECTION B: HOURS CALCULATION ===
  ├─ Count total sessions
  ├─ Sum all session_duration values → total_hours_taught
  │
  ├─ === SECTION C: STUDENT STATS (Crash-Proof Loop) ===
  ├─ Fetch ALL AttendanceRecords for these sessions (select_related: student, session)
  ├─ Initialize student_map = {}
  ├─ For each ACTIVE student in students:
  │  └─ Add to map: {reg_no: {obj, present_hours: 0, total_hours: 0}}
  ├─ For each AttendanceRecord:
  │  ├─ Get student's reg_no
  │  ├─ CRITICAL CHECK: Is reg_no in map?
  │  │  ├─ NO: Add to map (handles deleted/late-joined students)
  │  │  └─ YES: Continue
  │  ├─ Increment student's total_hours += session.session_duration
  │  ├─ If status in ['Present', 'OD']:
  │  │  └─ Increment present_hours += session.session_duration
  │
  ├─ === SECTION D: BUILD FINAL LISTS ===
  ├─ actual_student_count = len(student_map)
  ├─ Initialize student_stats = [], defaulters = []
  ├─ For each (reg_no, data) in student_map.items():
  │  ├─ attended_hours = data['present_hours']
  │  ├─ base_hours = data['total_hours'] (or global if course_id)
  │  ├─ Calculate pct = (attended_hours / base_hours) * 100 if base > 0
  │  ├─ severity = "Critical" if pct < 75 else "Safe"
  │  ├─ Build stat_obj with all details
  │  ├─ Add to student_stats
  │  ├─ If pct < 75: Add to defaulters
  │
  ├─ === SECTION E: CHARTS DATA ===
  ├─ If course_id (Subject View):
  │  ├─ Count records by status: Present, OD, Absent
  │  └─ pie_data = [present_count, od_count, absent_count]
  ├─ Else (Admin View):
  │  ├─ safe_count = actual_student_count - len(defaulters)
  │  └─ pie_data = [safe_count, len(defaulters)]
  ├─ Trend Data (Last 7 Days):
  │  ├─ Get unique dates from sessions (DESC order, first 7)
  │  ├─ Sort chronologically
  │  ├─ For each date:
  │  │  ├─ Filter sessions by date
  │  │  ├─ Count Present+OD vs Total records
  │  │  ├─ Calculate daily_avg_pct
  │  │  └─ Add to trend_data & trend_labels
  ├─ History Data (Last 15 Sessions):
  │  ├─ Get 15 most recent sessions
  │  ├─ For each session:
  │  │  ├─ Count Present, OD, Absent records
  │  │  └─ Build history_obj
  │
  ├─ === BUILD FINAL RESPONSE ===
  ├─ Return JSON:
  │  ├─ meta: {title, subtitle, course_id, faculty_name}
  │  ├─ stats: {total_students, total_sessions, total_hours}
  │  ├─ charts: {trend_labels, trend_data, pie_data}
  │  ├─ defaulters: [...list of students < 75%]
  │  ├─ leaderboard: [sorted by % DESC]
  │  └─ history: [...recent sessions]
  │
  └─ CATCH any Exception → log & return error JSON
END

CRITICAL FIX: Crash-Proof Student Map Handling
- Initialize map with ACTIVE students only
- When processing records: Check if reg_no in map
- If NOT found: Add to map (handles deleted/transferred students)
- Ensures attendance history is preserved even if student deleted later
```

---

## Semester Views

### 58. send_delete_otp_api()
```
START (POST)
  ├─ Get college_id from session
  │  └─ NOT present: Unauthorized
  ├─ Generate OTP
  ├─ Store in session (delete_otp, delete_verified=False)
  ├─ Send email to college admin
  └─ Return success
END
```

### 59. verify_delete_otp_api()
```
START (POST)
  ├─ Get OTP from JSON
  ├─ Compare with session OTP
  │  ├─ Match?
  │  │  ├─ YES: delete_verified=True
  │  │  └─ NO: Error
  └─ END
END
```

### 60. delete_department_api()
```
START (@csrf_exempt, @transaction.atomic, POST, JSON)
  ├─ Check delete_verified flag
  │  └─ NOT verified: Unauthorized
  ├─ Get dept_id
  ├─ Delete Department
  ├─ Invalidate cache
  ├─ Reset verification
  └─ Return success
END
```

### 61. delete_class_admin_api()
```
START (@csrf_exempt, @transaction.atomic, POST, JSON)
  ├─ Check delete_verified flag
  ├─ Get class_id
  ├─ Delete AcademicClass
  ├─ Invalidate cache
  ├─ Reset verification
  └─ Return success
END
```

### 62. send_action_otp_api()
```
START (POST)
  ├─ Get college_id
  ├─ Get action_type (student/faculty/class), target_id, extra_data
  ├─ Generate OTP
  ├─ Save context to session (otp, action, target_id, extra, verified=False)
  ├─ Send email to college admin
  └─ Return success
END
```

### 63. verify_action_and_execute_api()
```
START (@csrf_exempt, POST, JSON)
  ├─ Get OTP from JSON
  ├─ Verify against session OTP
  │  └─ NOT match: Error
  ├─ Get action type from session context
  │  ├─ If action='student':
  │  │  ├─ Soft delete main student record
  │  │  ├─ Find and deactivate shadow copies in courses
  │  │  └─ Notify faculty and invalidate caches
  │  ├─ If action='class':
  │  │  ├─ Delete AcademicClass
  │  │  └─ Invalidate cache
  │  ├─ If action='faculty':
  │  │  ├─ Delete join requests
  │  │  ├─ Send termination notifications
  │  │  ├─ Handle course reassignment or orphaning
  │  │  └─ Unlink from college
  ├─ Clear session context
  └─ Return success message
END
```

### 64. send_add_dept_otp_api()
```
START (POST)
  ├─ Get college_id
  ├─ Generate OTP
  ├─ Store in session
  ├─ Send email
  └─ Return success
END
```

### 65. verify_add_dept_otp_api()
```
START (POST, JSON)
  ├─ Get OTP from JSON
  ├─ Compare with session OTP
  │  ├─ Match?
  │  │  ├─ YES: add_dept_verified=True
  │  │  └─ NO: Error
  └─ END
END
```

### 66. send_start_sem_otp()
```
START (@csrf_exempt, POST, JSON)
  ├─ Get college_id
  ├─ Get semester (1-8), class_id, start_date, end_date
  ├─ Validate semester range
  ├─ Generate OTP
  ├─ Store context in session (class_id, new_sem, dates, otp, timestamp)
  ├─ Send email to admin
  └─ Return success
END
```

### 67. verify_start_sem_api()
```
START (@csrf_exempt, @transaction.atomic, POST, JSON)
  ├─ Get OTP and verify against session
  ├─ Get context from session
  ├─ Query AcademicClass
  ├─ Update current_semester and current_year
  ├─ Set semester dates
  ├─ Save
  ├─ Clear session
  ├─ Invalidate cache
  └─ Return success with new year
END
```

### 68. send_end_sem_otp()
```
START (@csrf_exempt, POST, JSON)
  ├─ Get class_id
  ├─ Verify class has active semester
  │  └─ NO: Error
  ├─ Generate OTP
  ├─ Store context (class_id, otp, timestamp)
  ├─ Send email with warning
  └─ Return success
END
```

### 69. execute_end_semester()
```
START (@csrf_exempt, @transaction.atomic, POST, JSON)
  ├─ Verify OTP
  ├─ Get AcademicClass
  ├─ Archive active courses (mark inactive, stamp semester)
  ├─ Set current_semester=None
  ├─ Save
  ├─ Clear session and cache
  └─ Return success with course count
END
```

### 70. archive_class_api()
```
START (@csrf_exempt, @transaction.atomic, POST, JSON)
  ├─ Set AcademicClass.is_active=False
  ├─ Set all students in class to is_active=False
  ├─ [Additional logic...]
  └─ Return success
END
```

---

## Student Views

### 71. send_resign_otp()
```
START (POST)
  ├─ Get faculty_id from session
  │  └─ NOT present: Unauthorized
  ├─ Query NewFaculty
  ├─ Check if linked to college
  │  └─ NO: Error
  ├─ Generate OTP
  ├─ Store in session
  ├─ Send email
  └─ Return success
END
```

### 72. leave_college_api()
```
START (@csrf_exempt, @transaction.atomic, POST, JSON)
  ├─ Get OTP from JSON
  ├─ Verify against session OTP
  │  └─ NOT match: Error
  ├─ Get faculty_id
  ├─ Query NewFaculty
  ├─ Unlink department
  ├─ Orphan all courses (faculty=None)
  ├─ Create college notification
  ├─ Invalidate caches
  ├─ Clear session OTP
  └─ Return success
END
```

### 73. student_portal_view()
```
START (GET)
  └─ Render student_portal.html
END
```

### 74. public_get_college_depts()
```
START (@csrf_exempt, GET)
  ├─ Get college_code from query
  ├─ Query College by code
  │  ├─ Found:
  │  │  ├─ Get departments
  │  │  └─ Return {found: true, college_name, departments: []}
  │  └─ NOT found: Return {found: false, error}
  └─ END
END
```

### 75. public_get_student_profile()
```
START (@csrf_exempt, POST, JSON)
  ├─ Get college_code, dept_id, reg_no from JSON
  ├─ Query College by code
  ├─ Query Department (verify college ownership)
  ├─ Query Student (case-insensitive reg_no, active only)
  │  └─ NOT found: 404
  ├─ Get enrolled courses (active)
  ├─ For each course:
  │  ├─ Get total hours and sessions
  │  ├─ Get student's hours (present, od, absent)
  │  ├─ Calculate percentage
  │  └─ Append to per_course
  ├─ Calculate overall stats
  ├─ Calculate safe skip logic
  └─ Return JSON with full profile
END
```

### 76. promote_class()
```
START (POST)
  ├─ Get class_id
  ├─ Query AcademicClass
  ├─ If current_year < 4:
  │  ├─ Increment current_year
  │  ├─ Save
  │  └─ Return promoted message
  ├─ Else: Return graduation message
  └─ END
```

---

## Timetable Views

### 77. calculate_semester_stats_api()
```
START (POST, JSON)
  ├─ Get start_date, end_date, active_days
  ├─ Parse dates
  ├─ Count working days based on active days
  ├─ Calculate weeks (working_days / days_per_week)
  └─ Return JSON with working_days and total_weeks
END
```

### 78. init_timetable_api()
```
START (@csrf_exempt, GET)
  ├─ Get class_id from query
  │  └─ Invalid: Error
  ├─ Query AcademicClass
  ├─ Get or Create TimeTableSettings
  ├─ Calculate date range and weeks
  ├─ Get valid semesters for this year
  ├─ Get all courses for this class
  ├─ For each course:
  │  ├─ Get faculty name
  │  ├─ Calculate weekly_hours_needed
  │  └─ Add to subject_load
  ├─ Get missing department subjects (unassigned)
  ├─ Get existing TimeTableSlot entries
  └─ Return JSON with all timetable data
END
```

### 79. check_faculty_conflict_api()
```
START (@csrf_exempt, POST, JSON)
  ├─ Get faculty_id, day, period, class_id
  ├─ If no faculty_id: No conflict
  ├─ Search for TimeTableSlot in OTHER classes at same time
  │  ├─ Found:
  │  │  ├─ Extract faculty, class, subject names (with safety)
  │  │  └─ Return {conflict: true, message}
  │  └─ NOT found: Return {conflict: false}
  └─ END
END
```

### 80. save_timetable_slot_api()
```
START (@csrf_exempt, POST, JSON)
  ├─ Get class_id, day, period, subject_id
  ├─ Update or create TimeTableSlot
  ├─ Set is_break=False
  └─ Return success
END
```

### 81. save_timetable_settings_api()
```
START (POST, JSON)
  ├─ Get class_id
  ├─ Query TimeTableSettings
  │  └─ NOT found: 404
  ├─ Parse and update dates
  ├─ Update periods_per_day
  ├─ Update working_days
  ├─ Save
  └─ Return success
END
```

### 82. get_suggested_session_api()
```
START (GET, @csrf_exempt)
  ├─ Get course_id and date
  ├─ Query Course
  ├─ Calculate day of week
  ├─ Search TimeTableSlot matching:
  │  ├─ class_name, day, subject_code
  ├─ If found:
  │  ├─ Return {found: true, start, end, message}
  ├─ Else:
  │  └─ Return {found: false}
  └─ END
END
```

---

## Utility Functions (utils.py)

### 83. rate_limit() [Decorator]
```
START (Function call wrapped with decorator)
  ├─ Skip if DEBUG mode
  ├─ Get client IP
  ├─ Create cache_key: "rate_limit:{prefix}:{ip}"
  ├─ Get current attempts from cache
  ├─ If attempts >= max_attempts:
  │  └─ Return HTTP 429 Too Many Requests
  ├─ Increment attempts in cache
  ├─ Call original view function
  └─ END
```

### 84. validate_email()
```
START (Input: email_string)
  ├─ Check if empty or too long (> 254)
  ├─ Validate format with regex
  ├─ HTML escape
  └─ Return sanitized email
END
```

### 85. validate_password()
```
START (Input: password_string)
  ├─ Check length (8-128 characters)
  ├─ Check for uppercase letter
  ├─ Check for lowercase letter
  ├─ Check for digit
  └─ Return password (not hashed)
END
```

### 86. validate_name()
```
START (Input: name_string)
  ├─ Check length (< 100)
  ├─ Validate characters (letters, spaces, hyphens, apostrophes)
  ├─ HTML escape
  └─ Return sanitized name
END
```

### 87. validate_reg_no()
```
START (Input: reg_no_string)
  ├─ Check length (< 50)
  ├─ Validate format (alphanumeric, hyphens, underscores)
  ├─ HTML escape
  ├─ Convert to uppercase
  └─ Return cleaned reg_no
END
```

### 88. sanitize_html_input()
```
START (Input: input_string, max_length)
  ├─ Check if empty
  ├─ Check length against max_length
  ├─ HTML escape
  └─ Return sanitized input
END
```

### 89. invalidate_faculty_dashboard_cache()
```
START (Input: faculty_id)
  ├─ If faculty_id exists:
  │  └─ Delete cache key: "faculty_dashboard:{faculty_id}"
  └─ END
```

### 90. invalidate_college_dashboard_cache()
```
START (Input: college_id)
  ├─ If college_id exists:
  │  └─ Delete cache key: "college_dashboard:{college_id}"
  └─ END
```

### 91. invalidate_user_caches()
```
START (Input: request)
  ├─ Get faculty_id and college_id from session
  ├─ Call invalidate_faculty_dashboard_cache()
  ├─ Call invalidate_college_dashboard_cache()
  └─ END
```

---

## Legend & Symbols

- **START/END**: Entry and exit points of a function
- **├─**: Sequential step or operation
- **│**: Continuation line
- **YES/NO**: Decision/conditional branch
- **→**: Result or output
- **@decorator**: Decorators applied to function
- **CATCH**: Exception handling block
- **DB query**: Database operation
- **Cache**: Data caching operation
- **Notification**: User/system notification

---

## Key Flow Patterns

### Authentication Pattern
```
Validate Input → Check Rate Limit → Query DB → Verify Credentials → 
Session Management → Return Response
```

### OTP Pattern
```
Generate OTP → Store in Cache/Session → Send Email → 
Verify Against Stored → Clear on Success → Return Status
```

### CRUD Pattern
```
Authorization Check → Input Validation → Duplicate/Conflict Check → 
DB Operation → Cache Invalidation → Return Result
```

### Cache Pattern
```
Check Cache → If Hit: Return → If Miss: Query DB → 
Store in Cache → Return → (Set Expiry: 5-10 min)
```

### Notification Pattern
```
Create Notification Record → Send Email → Dashboard Notification → 
Optional DB Record → Return Status
```

---

## Statistics

- **Total Functions Documented**: 91
- **Files Covered**: 11 view files + utils.py
- **Decorators Used**: @csrf_exempt, @rate_limit, @transaction.atomic, @ensure_csrf_cookie, @never_cache
- **Key Operations**: Authentication, CRUD, Caching, OTP Verification, Notifications
- **Response Types**: JSON, HTML, CSV, Session-based, JWT Tokens
