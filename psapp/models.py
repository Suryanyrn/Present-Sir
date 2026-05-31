from django.db import models
from django.utils import timezone
from django.db.models import Index, Q
from django.core.exceptions import ValidationError
import json

# ==========================================
#  COLLEGE HIERARCHY MODELS
# ==========================================

class College(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    college_name = models.CharField(max_length=200)
    college_code = models.CharField(max_length=20, unique=True) # Unique ID
    website = models.URLField(max_length=200)

    # Admin Credentials
    admin_email = models.EmailField(unique=True)
    password = models.CharField(max_length=128)

    # Status
    is_verified = models.BooleanField(default=False)
    is_approved = models.BooleanField(default=True)

    class Meta:
        indexes = [
            Index(fields=['admin_email']),  # Login queries
            Index(fields=['college_code']),  # College lookups
            Index(fields=['is_verified']),  # Filtering verified colleges
        ] 

    def save(self, *args, **kwargs):
        if self.password:
            try:
                from django.contrib.auth.hashers import identify_hasher
                identify_hasher(self.password)
            except ValueError:
                from django.contrib.auth.hashers import make_password
                self.password = make_password(self.password)
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.college_name} ({self.college_code})"

class Department(models.Model):
    college = models.ForeignKey(College, on_delete=models.CASCADE, related_name='departments')
    name = models.CharField(max_length=100)
    established_year = models.IntegerField(default=2024)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name

class DepartmentCourse(models.Model):
    department = models.ForeignKey(Department, on_delete=models.CASCADE, related_name='courses')
    course_name = models.CharField(max_length=150)
    course_code = models.CharField(max_length=50)
    semester = models.IntegerField(default=0, null=True, blank=True)
    course_type = models.CharField(
        max_length=20, 
        choices=[('Core', 'Core Subject'), ('Elective', 'Elective Subject'), ('Lab', 'Practical/Lab')],
        default='Core'
    )
    class Meta:
        ordering =['semester', 'course_name']
    
    def __str__(self):
        return f"{self.course_code} ({self.course_type}) - Sem {self.semester}"

class AcademicClass(models.Model):
    department = models.ForeignKey(Department, on_delete=models.CASCADE, related_name='classes')
    class_name = models.CharField(max_length=100) # e.g. "B.Tech CSE"
    section = models.CharField(max_length=10, default="A") # NEW: "A", "B", "C"
    academic_year = models.CharField(max_length=20) # e.g. "2024-2028"
    current_year = models.IntegerField(default=1)
    current_semester = models.IntegerField(null=True, blank=True) # Null means "Semester Break"
    semester_start_date = models.DateField(null=True, blank=True)
    semester_end_date = models.DateField(null=True, blank=True)
    is_active = models.BooleanField(default=True) # NEW: False = Alumni/Graduated
    created_at = models.DateTimeField(auto_now_add=True)
    
    def get_status(self):
        if not self.is_active:
            return "Archived"
        return "Active" if self.current_semester else "Semester Break"

    class Meta:
        indexes = [
            Index(fields=['department']),
            Index(fields=['class_name']),
            Index(fields=['current_year']),
            Index(fields=['is_active']), # Useful for filtering out alumni
        ]
        # NEW CONSTRAINT: Class + Section + Batch must be unique within a Department
        unique_together = ('department', 'class_name', 'section', 'academic_year')

    def __str__(self):
        return f"{self.class_name} - Sec {self.section} ({self.academic_year})"

# ==========================================
#  FACULTY MODELS
# ==========================================

class NewFaculty(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    college_name = models.CharField(max_length=150)
    name = models.CharField(max_length=100)
    department = models.CharField(max_length=100) # Text field (Legacy/Signup)
    designation = models.CharField(max_length=50)
    college_email = models.EmailField(unique=True)
    mobile_num = models.CharField(max_length=15)
    password = models.CharField(max_length=128)
    faculty_reg_id = models.CharField(max_length=20, unique=True, null=True, blank=True)
    profile_photo = models.ImageField(upload_to='faculty_photos/', null=True, blank=True)
    otp = models.CharField(max_length=6, null=True, blank=True)
    is_verified = models.BooleanField(default=False)

    # Link to actual Department Object (Admin Logic)
    department_link = models.ForeignKey('Department', on_delete=models.SET_NULL, null=True, blank=True, related_name='faculty_members')

    class Meta:
        indexes = [
            Index(fields=['college_email']),  # Login queries
            Index(fields=['faculty_reg_id']),  # Faculty search by ID
            Index(fields=['is_verified']),  # Filtering verified faculty
            Index(fields=['department_link']),  # Department-based queries
            Index(fields=['college_name']),  # College-based filtering
        ]

    def save(self, *args, **kwargs):
        if self.password:
            try:
                from django.contrib.auth.hashers import identify_hasher
                identify_hasher(self.password)
            except ValueError:
                from django.contrib.auth.hashers import make_password
                self.password = make_password(self.password)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name


class FacultyJoinRequest(models.Model):
    college = models.ForeignKey(College, on_delete=models.CASCADE)
    department = models.ForeignKey(Department, on_delete=models.CASCADE)
    faculty = models.ForeignKey(NewFaculty, on_delete=models.CASCADE, related_name='join_requests')
    status = models.CharField(max_length=20, default='Pending') # Pending, Approved, Rejected
    created_at = models.DateTimeField(auto_now_add=True)

# ==========================================
#  FACULTY DASHBOARD / CLASSROOM MODELS
# ==========================================

# 2. Represents the Students
class Student(models.Model):
    # 1. LINK TO MASTER STRUCTURE
    college = models.ForeignKey(College, on_delete=models.CASCADE, related_name='all_students', null=True, blank=True)
    academic_class = models.ForeignKey(AcademicClass, on_delete=models.SET_NULL, null=True, blank=True, related_name='students')
    
    # 2. STUDENT DATA
    name = models.CharField(max_length=100)
    reg_no = models.CharField(max_length=50) # Normalized (Upper Case)
    email = models.EmailField(null=True, blank=True)
    student_type = models.CharField(
        max_length=20, 
        choices=[('Official', 'Official'), ('Personal', 'Personal')], 
        default='Official'
    )
    created_by_faculty = models.ForeignKey(NewFaculty, on_delete=models.CASCADE, null=True, blank=True)
    joined_at = models.DateField(default=timezone.now)
    is_active = models.BooleanField(default=True)

    class Meta:
        indexes = [
            models.Index(fields=['reg_no']),
            models.Index(fields=['student_type']),
            models.Index(fields=['created_by_faculty']),
        ]
        unique_together = ('college', 'reg_no')

    def __str__(self):
        return f"{self.name} ({self.student_type})"
class Course(models.Model):
    # Standard Fields
    academic_class = models.ForeignKey(AcademicClass, on_delete=models.SET_NULL, null=True, blank=True, related_name='assigned_courses')
    faculty = models.ForeignKey(NewFaculty, on_delete=models.SET_NULL, null=True, blank=True)
    class_name = models.CharField(max_length=100)
    course_type = models.CharField(
        max_length=20, 
        choices=[('Core', 'Core'), ('Elective', 'Elective'), ('Lab', 'Lab')],
        default='Core'
    )
    batch_name = models.CharField(max_length=50, default="Main", help_text="e.g., 'Group A', 'Batch 1', or 'Main'")
    subject_name = models.CharField(max_length=100)
    subject_code = models.CharField(max_length=50)
    semester = models.IntegerField(default=1, null=True, blank=True)
    is_personal = models.BooleanField(default=False)
    parent_course_id = models.IntegerField(null=True, blank=True)
    
    # 4. THE MAGIC LINK (No more shadow copies)
    # This creates a hidden table mapping Course IDs to Student IDs
    enrolled_students = models.ManyToManyField(Student, related_name='enrolled_courses', blank=True)
    
    total_hours = models.IntegerField(default=45)
    is_assigned = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.subject_name} ({self.batch_name})"

class AttendanceSession(models.Model):
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name='sessions')
    date = models.DateField()
    created_at = models.DateTimeField(auto_now_add=True)

    # Analytics (Stored to avoid recalculating every time)
    total_present = models.IntegerField(default=0)
    total_absent = models.IntegerField(default=0)
    
    start_session = models.IntegerField(default=1)
    end_session = models.IntegerField(default=1)
    session_duration = models.IntegerField(default=1)
    current_semester = models.IntegerField(default=1)

    def clean(self):
        """
        CRITICAL LOGIC FIX: Prevents overlapping sessions.
        """
        # Exclude self if editing to allow saving updates to the same instance
        overlapping = AttendanceSession.objects.filter(
            course=self.course,
            date=self.date,
            start_session__lte=self.end_session, # Existing start <= New end
            end_session__gte=self.start_session  # Existing end >= New start
        ).exclude(id=self.id) 

        if overlapping.exists():
            overlap = overlapping.first()
            overlap_details = f"{overlap.start_session}-{overlap.end_session}"
            raise ValidationError(f"Time slot Conflict! Attendance already marked for periods {overlap_details}.")

    def save(self, *args, **kwargs):
        # Auto-calculate session duration
        if self.end_session >= self.start_session:
            self.session_duration = self.end_session - self.start_session + 1
        
        # Run validation before saving
        self.clean()
        super().save(*args, **kwargs)

    class Meta:
        indexes = [
            Index(fields=['course', 'date']),
            Index(fields=['date']),
            Index(fields=['course']),
            Index(fields=['created_at']),
        ]
        # Unique constraint to ensure DB level integrity
        unique_together = ('course', 'date', 'start_session', 'end_session')
# 4. Represents individual status
class AttendanceRecord(models.Model):
    session = models.ForeignKey(AttendanceSession, on_delete=models.CASCADE, related_name='records')
    student = models.ForeignKey(Student, on_delete=models.CASCADE)
    status = models.CharField(max_length=10, choices=[('Present', 'Present'), ('Absent', 'Absent'), ('OD', 'On Duty')])
    
    def save(self, *args, **kwargs):
        # Only check enrollment if this is a NEW record (no Primary Key yet)
        if not self.pk: 
            is_enrolled = self.session.course.enrolled_students.filter(id=self.student.id).exists()
            if not is_enrolled:
                raise ValueError(f"Student {self.student.reg_no} is not enrolled...")
    
        super().save(*args, **kwargs)

    class Meta:
        indexes = [
            Index(fields=['session', 'student']),
            Index(fields=['student', 'status']), # Speed up dashboard stats
        ]
        unique_together = ('session', 'student')  # Prevent duplicate records
    
class CollegeNotification(models.Model):
    college = models.ForeignKey(College, on_delete=models.CASCADE, related_name='notifications')
    message = models.CharField(max_length=255)
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.college.college_name} - {self.message}"
    
class FacultyNotification(models.Model):
    faculty = models.ForeignKey(NewFaculty, on_delete=models.CASCADE, related_name='notifications')
    message = models.CharField(max_length=255)
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"To {self.faculty.name}: {self.message}"

# models.py

class ClassAssignmentRequest(models.Model):
    # Who is asking?
    college = models.ForeignKey(College, on_delete=models.CASCADE)
    
    # Who is being asked?
    faculty = models.ForeignKey(NewFaculty, on_delete=models.CASCADE)
    
    # What are they teaching?
    academic_class = models.ForeignKey(AcademicClass, on_delete=models.CASCADE)
    subject = models.ForeignKey(DepartmentCourse, on_delete=models.CASCADE)
    total_hours = models.IntegerField(default=45)
    
    batch_name = models.CharField(max_length=50, null=True, blank=True)
    student_list_json = models.TextField(null=True, blank=True) 
    
    status = models.CharField(max_length=20, default='Pending') # Pending, Approved, Rejected, Revoked
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Req: {self.faculty.name} -> {self.subject.course_name}"    
# Add this to your models.py

class TimeTableSettings(models.Model):
    academic_class = models.OneToOneField(AcademicClass, on_delete=models.CASCADE, related_name='timetable_settings')
    semester_start = models.DateField()
    semester_end = models.DateField()
    working_days = models.TextField(default='["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]')
    periods_per_day = models.IntegerField(default=7)
    break_after_period = models.IntegerField(default=0) # 0 means no fixed break
    
    # Helper methods to handle the List <-> String conversion
    def get_working_days(self):
        try:
            return json.loads(self.working_days)
        except:
            return []

    def set_working_days(self, days_list):
        if not isinstance(days_list, list):
            raise ValidationError("Days must be a list")
        self.working_days = json.dumps(days_list)
    
class TimeTableSlot(models.Model):
    academic_class = models.ForeignKey(AcademicClass, on_delete=models.CASCADE)
    day = models.CharField(max_length=15) # "Monday", etc.
    period_number = models.IntegerField() # 1, 2, 3...
    subject = models.ForeignKey(Course, on_delete=models.SET_NULL, null=True)
    is_break = models.BooleanField(default=False)

    class Meta:
        unique_together = ('academic_class', 'day', 'period_number')
