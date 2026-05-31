"""
Comprehensive Test Suite for PresentSir Application
Tests all major functions in views.py to ensure they work logically
"""

from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth.hashers import make_password
from datetime import date, datetime, timedelta
import json

from .models import (
    College, NewFaculty, Department, AcademicClass, Course, Student,
    AttendanceSession, AttendanceRecord, FacultyNotification, 
    CollegeNotification, ClassAssignmentRequest, FacultyJoinRequest,
    DepartmentCourse
)


class AuthenticationTests(TestCase):
    """Test authentication functions"""
    
    def setUp(self):
        self.client = Client()
        self.faculty = NewFaculty.objects.create(
            name="Test Faculty",
            college_email="test@test.com",
            password=make_password("password123"),
            college_name="Test College",
            department="Test Dept",
            designation="Professor",
            mobile_num="1234567890",
            is_verified=True
        )
    
    def test_login_success(self):
        """Test successful login"""
        response = self.client.post(reverse('psapp:login'), {
            'email': 'test@test.com',
            'password': 'password123'
        })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content.decode(), 'LOGIN_SUCCESS')
        self.assertEqual(self.client.session.get('faculty_id'), self.faculty.id)
    
    def test_login_invalid_password(self):
        """Test login with wrong password"""
        response = self.client.post(reverse('psapp:login'), {
            'email': 'test@test.com',
            'password': 'wrongpassword'
        })
        self.assertEqual(response.content.decode(), 'INVALID')
        self.assertIsNone(self.client.session.get('faculty_id'))
    
    def test_login_unverified_user(self):
        """Test login with unverified user"""
        self.faculty.is_verified = False
        self.faculty.save()
        response = self.client.post(reverse('psapp:login'), {
            'email': 'test@test.com',
            'password': 'password123'
        })
        self.assertEqual(response.content.decode(), 'NOT_VERIFIED')
    
    def test_login_nonexistent_user(self):
        """Test login with non-existent email"""
        response = self.client.post(reverse('psapp:login'), {
            'email': 'nonexistent@test.com',
            'password': 'password123'
        })
        self.assertEqual(response.content.decode(), 'INVALID')


class DashboardTests(TestCase):
    """Test dashboard functions"""
    
    def setUp(self):
        self.client = Client()
        self.college = College.objects.create(
            college_name="Test College",
            college_code="TC01",
            admin_email="admin@test.com",
            password=make_password("admin123"),
            is_verified=True,
            is_approved=True
        )
        self.dept = Department.objects.create(
            college=self.college,
            name="CSE",
            established_year=2000
        )
        self.faculty = NewFaculty.objects.create(
            name="Faculty X",
            college_email="fac@test.com",
            faculty_reg_id="PS-FAC-1",
            college_name=self.college.college_name,
            department_link=self.dept,
            password=make_password("fac123"),
            is_verified=True
        )
        self.ac_class = AcademicClass.objects.create(
            department=self.dept,
            class_name="B.Tech CSE",
            academic_year="2022",
            current_year=2
        )
        self.course = Course.objects.create(
            faculty=self.faculty,
            class_name=self.ac_class.class_name,
            subject_name="Maths",
            subject_code="MATH101",
            total_hours=45,
            is_assigned=True
        )
        self.student = Student.objects.create(
            name="Student A",
            reg_no="S001",
            email="a@test.com",
            academic_class=self.ac_class,
            is_active=True
        )
        self.course.enrolled_students.add(self.student)
        
        # Set session
        session = self.client.session
        session['faculty_id'] = self.faculty.id
        session.save()
    
    def test_get_dashboard_data(self):
        """Test getting dashboard data"""
        response = self.client.get(reverse('psapp:get_dashboard_data'))
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn('classes', data)
        self.assertIn('faculty_photo', data)
        self.assertIn('faculty_id', data)
        self.assertEqual(len(data['classes']), 1)
        self.assertEqual(data['classes'][0]['subjectName'], 'Maths')
    
    def test_get_dashboard_data_unauthorized(self):
        """Test dashboard data without login"""
        client = Client()
        response = client.get(reverse('psapp:get_dashboard_data'))
        self.assertEqual(response.status_code, 401)
        self.assertIn('error', response.json())


class ClassManagementTests(TestCase):
    """Test class creation and management"""
    
    def setUp(self):
        self.client = Client()
        self.faculty = NewFaculty.objects.create(
            name="Test Faculty",
            college_email="faculty@test.com",
            password=make_password("pass"),
            college_name="Test College",
            department="Test Dept",
            designation="Professor",
            mobile_num="1234567890",
            is_verified=True
        )
        session = self.client.session
        session['faculty_id'] = self.faculty.id
        session.save()
    
    def test_create_class_api(self):
        """Test creating a new class"""
        data = {
            'className': 'Test Class',
            'subjectName': 'Test Subject',
            'subjectCode': 'TEST101',
            'totalHours': 45,
            'students': [
                {'regNo': 'S001', 'name': 'Student 1', 'email': 's1@test.com'},
                {'regNo': 'S002', 'name': 'Student 2', 'email': 's2@test.com'}
            ]
        }
        response = self.client.post(
            reverse('psapp:create_class_api'),
            data=json.dumps(data),
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 200)
        result = response.json()
        self.assertIn('message', result)
        self.assertIn('id', result)
        
        # Verify course was created
        course = Course.objects.get(id=result['id'])
        self.assertEqual(course.class_name, 'Test Class')
        self.assertEqual(course.subject_name, 'Test Subject')
        
        # Verify students were created
        students = course.enrolled_students.all()
        self.assertEqual(students.count(), 2)
    
    def test_create_class_duplicate_reg_no(self):
        """Test creating class with duplicate registration numbers"""
        data = {
            'className': 'Test Class',
            'subjectName': 'Test Subject',
            'subjectCode': 'TEST101',
            'totalHours': 45,
            'students': [
                {'regNo': 'S001', 'name': 'Student 1', 'email': 's1@test.com'},
                {'regNo': 'S001', 'name': 'Student 2', 'email': 's2@test.com'}  # Duplicate
            ]
        }
        response = self.client.post(
            reverse('psapp:create_class_api'),
            data=json.dumps(data),
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 400)
        result = response.json()
        self.assertIn('error', result)
        self.assertIn('Duplicate', result['error'])


class AttendanceTests(TestCase):
    """Test attendance functions"""
    
    def setUp(self):
        self.client = Client()
        self.faculty = NewFaculty.objects.create(
            name="Test Faculty",
            college_email="faculty@test.com",
            password=make_password("pass"),
            college_name="Test College",
            department="Test Dept",
            designation="Professor",
            mobile_num="1234567890",
            is_verified=True
        )
        self.course = Course.objects.create(
            faculty=self.faculty,
            class_name="Test Class",
            subject_name="Test Subject",
            subject_code="TEST101",
            total_hours=45
        )
        self.student1 = Student.objects.create(
            name="Student 1",
            reg_no="S001",
            email="s1@test.com",
            is_active=True
        )
        self.student2 = Student.objects.create(
            name="Student 2",
            reg_no="S002",
            email="s2@test.com",
            is_active=True
        )
        self.course.enrolled_students.add(self.student1, self.student2)
        
        session = self.client.session
        session['faculty_id'] = self.faculty.id
        session.save()
    
    def test_save_attendance_api(self):
        """Test saving attendance"""
        data = {
            'classId': self.course.id,
            'date': str(date.today()),
            'startSession': 1,
            'endSession': 1,
            'records': [
                {'regNo': 'S001', 'status': 'Present'},
                {'regNo': 'S002', 'status': 'Absent'}
            ]
        }
        response = self.client.post(
            '/api/save-attendance/',
            data=json.dumps(data),
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 200)
        result = response.json()
        self.assertIn('message', result)
        
        # Verify session was created
        session = AttendanceSession.objects.filter(course=self.course).first()
        self.assertIsNotNone(session)
        self.assertEqual(session.date, date.today())
        
        # Verify records were created
        records = AttendanceRecord.objects.filter(session=session)
        self.assertEqual(records.count(), 2)
        present_record = records.filter(student=self.student1).first()
        self.assertEqual(present_record.status, 'Present')
    
    def test_save_attendance_session_overlap(self):
        """Test saving attendance with overlapping session"""
        # Create existing session
        existing_session = AttendanceSession.objects.create(
            course=self.course,
            date=date.today(),
            start_session=1,
            end_session=2,
            session_duration=2
        )
        
        # Try to create overlapping session
        data = {
            'classId': self.course.id,
            'date': str(date.today()),
            'startSession': 2,
            'endSession': 3,
            'records': [
                {'regNo': 'S001', 'status': 'Present'}
            ]
        }
        response = self.client.post(
            reverse('psapp:save_attendance_api'),
            data=json.dumps(data),
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 400)
        result = response.json()
        self.assertIn('error', result)
        self.assertIn('Conflict', result['error'])


class StudentManagementTests(TestCase):
    """Test student management functions"""
    
    def setUp(self):
        self.client = Client()
        self.college = College.objects.create(
            college_name="Test College",
            college_code="TC01",
            admin_email="admin@test.com",
            password=make_password("admin123"),
            is_verified=True,
            is_approved=True
        )
        self.dept = Department.objects.create(
            college=self.college,
            name="CSE",
            established_year=2000
        )
        self.faculty = NewFaculty.objects.create(
            name="Faculty X",
            college_email="fac@test.com",
            faculty_reg_id="PS-FAC-1",
            college_name=self.college.college_name,
            department_link=self.dept,
            password=make_password("fac123"),
            is_verified=True
        )
        self.ac_class = AcademicClass.objects.create(
            department=self.dept,
            class_name="B.Tech CSE",
            academic_year="2022",
            current_year=2
        )
        self.course = Course.objects.create(
            faculty=self.faculty,
            class_name=self.ac_class.class_name,
            subject_name="Maths",
            subject_code="MATH101",
            total_hours=45,
            is_assigned=True
        )
        self.student = Student.objects.create(
            name="Student A",
            reg_no="S001",
            email="a@test.com",
            academic_class=self.ac_class,
            is_active=True
        )
        self.course.enrolled_students.add(self.student)
        
        # Admin session
        session = self.client.session
        session['college_id'] = self.college.id
        session.save()
    
    def test_delete_student_api(self):
        """Test deleting a student"""
        # Count notifications before
        notif_count_before = FacultyNotification.objects.filter(faculty=self.faculty).count()
        
        response = self.client.post(
            reverse('psapp:delete_student_api'),
            data=json.dumps({'student_id': self.student.id}),
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 200)
        result = response.json()
        self.assertIn('message', result)
        
        # Verify student is marked inactive
        self.student.refresh_from_db()
        self.assertFalse(self.student.is_active)
        
        # Verify notification was sent
        notif_count_after = FacultyNotification.objects.filter(faculty=self.faculty).count()
        self.assertEqual(notif_count_after, notif_count_before + 1)
        
        # Verify notification content
        notification = FacultyNotification.objects.filter(faculty=self.faculty).latest('created_at')
        self.assertIn('STUDENT REMOVED', notification.message)
        self.assertIn(self.student.name, notification.message)
        self.assertIn(self.student.reg_no, notification.message)
    
    def test_get_student_stats_api(self):
        """Test getting student statistics"""
        # Create attendance session
        session = AttendanceSession.objects.create(
            course=self.course,
            date=date.today(),
            start_session=1,
            end_session=1,
            session_duration=1
        )
        AttendanceRecord.objects.create(
            session=session,
            student=self.student,
            status='Present'
        )
        
        response = self.client.get(reverse('psapp:get_student_stats_api', args=[self.student.id]))
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data['name'], 'Student A')
        self.assertEqual(data['regNo'], 'S001')
        self.assertIn('percentage', data)
        self.assertIn('per_course', data)
        self.assertIn('overall', data)


class CollegeAdminTests(TestCase):
    """Test college admin functions"""
    
    def setUp(self):
        self.client = Client()
        self.college = College.objects.create(
            college_name="Test College",
            college_code="TC01",
            admin_email="admin@test.com",
            password=make_password("admin123"),
            is_verified=True,
            is_approved=True
        )
        self.dept = Department.objects.create(
            college=self.college,
            name="CSE",
            established_year=2000
        )
        
        session = self.client.session
        session['college_id'] = self.college.id
        session.save()
    
    def test_get_college_dashboard_data(self):
        """Test getting college dashboard data"""
        response = self.client.get(reverse('psapp:get_college_data'))
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn('departments', data)
        self.assertIn('faculty', data)
        self.assertIn('stats', data)
    
    def test_add_academic_class_api(self):
        """Test adding academic class"""
        data = {
            'dept_id': self.dept.id,
            'name': 'B.Tech CSE 2024',
            'acad_year': '2024-2025',
            'currentYear': 1,
            'students': [
                {'regNo': 'S001', 'name': 'Student 1', 'email': 's1@test.com'},
                {'regNo': 'S002', 'name': 'Student 2', 'email': 's2@test.com'}
            ]
        }
        response = self.client.post(
            reverse('psapp:add_class'),
            data=json.dumps(data),
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 200)
        result = response.json()
        self.assertIn('message', result)
        
        # Verify class was created
        ac_class = AcademicClass.objects.filter(class_name='B.Tech CSE 2024').first()
        self.assertIsNotNone(ac_class)
        
        # Verify students were created
        students = Student.objects.filter(academic_class=ac_class)
        self.assertEqual(students.count(), 2)
    
    def test_add_academic_class_duplicate_name(self):
        """Test adding class with duplicate name"""
        # Create existing class
        AcademicClass.objects.create(
            department=self.dept,
            class_name="B.Tech CSE",
            academic_year="2022",
            current_year=2
        )
        
        data = {
            'dept_id': self.dept.id,
            'name': 'B.Tech CSE',  # Duplicate
            'acad_year': '2024-2025',
            'currentYear': 1,
            'students': []
        }
        response = self.client.post(
            reverse('psapp:add_class'),
            data=json.dumps(data),
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 400)
        result = response.json()
        self.assertIn('error', result)
        self.assertIn('already exists', result['error'])


class NotificationTests(TestCase):
    """Test notification functions"""
    
    def setUp(self):
        self.client = Client()
        self.college = College.objects.create(
            college_name="Test College",
            college_code="TC01",
            admin_email="admin@test.com",
            password=make_password("admin123"),
            is_verified=True,
            is_approved=True
        )
        self.dept = Department.objects.create(
            college=self.college,
            name="CSE",
            established_year=2000
        )
        self.faculty = NewFaculty.objects.create(
            name="Faculty X",
            college_email="fac@test.com",
            faculty_reg_id="PS-FAC-1",
            college_name=self.college.college_name,
            department_link=self.dept,
            password=make_password("fac123"),
            is_verified=True
        )
        self.ac_class = AcademicClass.objects.create(
            department=self.dept,
            class_name="B.Tech CSE",
            academic_year="2022",
            current_year=2
        )
        self.course = Course.objects.create(
            faculty=self.faculty,
            class_name=self.ac_class.class_name,
            subject_name="Maths",
            subject_code="MATH101",
            total_hours=45,
            is_assigned=True
        )
        
        # Faculty session
        self.faculty_client = Client()
        session = self.faculty_client.session
        session['faculty_id'] = self.faculty.id
        session.save()
    
    def test_get_faculty_notifications_api(self):
        """Test getting faculty notifications"""
        # Create notification
        FacultyNotification.objects.create(
            faculty=self.faculty,
            message="Test notification"
        )
        
        response = self.faculty_client.get(reverse('psapp:get_faculty_notifs'))
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn('notifications', data)
        self.assertEqual(len(data['notifications']), 1)
        self.assertEqual(data['notifications'][0]['message'], 'Test notification')
    
    def test_mark_notification_read(self):
        """Test marking notification as read"""
        notification = FacultyNotification.objects.create(
            faculty=self.faculty,
            message="Test notification"
        )
        
        response = self.faculty_client.post(
            reverse('psapp:mark_faculty_notif_read'),
            data=json.dumps({'id': notification.id}),
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 200)
        
        # Verify notification is marked as read
        notification.refresh_from_db()
        self.assertTrue(notification.is_read)


class EditProfileTests(TestCase):
    """Test profile editing functions"""
    
    def setUp(self):
        self.client = Client()
        self.faculty = NewFaculty.objects.create(
            name="Test Faculty",
            college_email="test@test.com",
            password=make_password("pass"),
            college_name="Test College",
            department="Test Dept",
            designation="Professor",
            mobile_num="1234567890",
            is_verified=True
        )
        
        session = self.client.session
        session['faculty_id'] = self.faculty.id
        session.save()
    
    def test_edit_profile_api(self):
        """Test editing faculty profile"""
        response = self.client.post(reverse('psapp:edit_profile_api'), {
            'name': 'Updated Name',
            'designation': 'Associate Professor',
            'mobile': '9876543210'
        })
        self.assertEqual(response.status_code, 200)
        result = response.json()
        self.assertIn('message', result)
        
        # Verify profile was updated
        self.faculty.refresh_from_db()
        self.assertEqual(self.faculty.name, 'Updated Name')
        self.assertEqual(self.faculty.designation, 'Associate Professor')
        self.assertEqual(self.faculty.mobile_num, '9876543210')


class DepartmentCourseTests(TestCase):
    """Test department course management"""
    
    def setUp(self):
        self.client = Client()
        self.college = College.objects.create(
            college_name="Test College",
            college_code="TC01",
            admin_email="admin@test.com",
            password=make_password("admin123"),
            is_verified=True,
            is_approved=True
        )
        self.dept = Department.objects.create(
            college=self.college,
            name="CSE",
            established_year=2000
        )
        
        session = self.client.session
        session['college_id'] = self.college.id
        session.save()
    
    def test_add_dept_course_api(self):
        """Test adding department course"""
        response = self.client.post(reverse('psapp:add_course'), {
            'dept_id': self.dept.id,
            'course_code': 'CS101',
            'course_title': 'Introduction to Programming',
            'semester': 1,
            'course_type': 'Core'
        })
        self.assertEqual(response.status_code, 200)
        result = response.json()
        self.assertIn('message', result)
        
        # Verify course was created
        course = DepartmentCourse.objects.filter(
            department=self.dept,
            course_code='CS101'
        ).first()
        self.assertIsNotNone(course)
        self.assertEqual(course.course_name, 'Introduction to Programming')
    
    def test_edit_dept_course_api(self):
        """Test editing department course"""
        course = DepartmentCourse.objects.create(
            department=self.dept,
            course_code='CS101',
            course_name='Intro to Programming',
            semester=1,
            course_type='Core'
        )
        
        response = self.client.post(reverse('psapp:edit_course'), {
            'course_id': course.id,
            'course_code': 'CS101',
            'course_title': 'Introduction to Computer Programming',
            'semester': 1,
            'course_type': 'Core'
        })
        self.assertEqual(response.status_code, 200)
        result = response.json()
        self.assertIn('message', result)
        
        # Verify course was updated
        course.refresh_from_db()
        self.assertEqual(course.course_name, 'Introduction to Computer Programming')
    
    def test_get_dept_courses_api(self):
        """Test getting department courses"""
        DepartmentCourse.objects.create(
            department=self.dept,
            course_code='CS101',
            course_name='Intro to Programming',
            semester=1,
            course_type='Core'
        )
        
        response = self.client.get(reverse('psapp:get_courses'), {'dept_id': self.dept.id})
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn('courses', data)
        self.assertEqual(len(data['courses']), 1)
        self.assertEqual(data['courses'][0]['code'], 'CS101')

