from django.core.management.base import BaseCommand
from django.test import Client
from django.urls import reverse
from django.contrib.auth.hashers import make_password
from psapp.models import College, NewFaculty, Department, Student
from django.db.utils import IntegrityError # Crucial Import
import json

class Command(BaseCommand):
    help = 'Runs a full system health check on URLs and Data Logic'

    def handle(self, *args, **kwargs):
        self.stdout.write(self.style.WARNING('--- STARTING SYSTEM HEALTH CHECK ---'))
        
        # 1. CLEANUP (Fixes the Zombie Data issue)
        self.cleanup_test_data()

        # 2. SETUP DATA
        college, faculty = self.setup_core_data()

        # 3. TEST AUTHENTICATION
        self.test_login_flow(college, faculty)

        # 4. TEST MODEL CONSTRAINTS (The Crash Fix)
        self.test_model_constraints(college)
        
        # 5. TEST FACULTY OPERATIONS (The New Test)
        self.test_faculty_operations(college, faculty)

        self.stdout.write(self.style.SUCCESS('--- HEALTH CHECK COMPLETED ---'))

    def cleanup_test_data(self):
        # Delete College (Cascades to Departments, Classes, Students)
        College.objects.filter(college_code="TEST001").delete()
        # Delete Orphaned Faculty
        NewFaculty.objects.filter(college_email="faculty@test.edu").delete()
        self.stdout.write("Old test data cleaned.")

    def setup_core_data(self):
        college = College.objects.create(
            college_name="Test Engineering College",
            college_code="TEST001",
            website="https://test.edu",
            admin_email="admin@test.edu",
            password=make_password("AdminPass123"),
            is_verified=True
        )
        
        dept = Department.objects.create(college=college, name="Computer Science")

        faculty = NewFaculty.objects.create(
            college_name=college.college_name,
            name="Test Faculty",
            department="Computer Science",
            department_link=dept,
            designation="AP",
            college_email="faculty@test.edu",
            mobile_num="1234567890",
            password=make_password("FacultyPass123"),
            is_verified=True
        )
        self.stdout.write(self.style.SUCCESS(f"✔ Data Setup: College & Faculty created."))
        return college, faculty

    def test_login_flow(self, college, faculty):
        c = Client()
        # Test Public URL
        try:
            response = c.get(reverse('psapp:index'))
            if response.status_code == 200:
                self.stdout.write(self.style.SUCCESS(f"✔ URL Check: Index Page (200 OK)"))
            else:
                self.stdout.write(self.style.ERROR(f"✘ URL Check: Index Page Failed ({response.status_code})"))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"✘ URL Check: Index crashed - {e}"))

    def test_model_constraints(self, college):
        self.stdout.write("Testing Student Constraints...")
        
        # Create first student (Should succeed)
        Student.objects.create(
            college=college,
            name="Student A",
            reg_no="95001",
            student_type="Official"
        )

        # Create duplicate student (Should fail and be caught)
        try:
            Student.objects.create(
                college=college,
                name="Student B",
                reg_no="95001", # Duplicate Reg No
                student_type="Official"
            )
            # If line above succeeds, the constraint is BROKEN
            self.stdout.write(self.style.ERROR("✘ CRITICAL: DB allowed duplicate Student Reg No!"))
        except IntegrityError:
            # If we land here, the constraint is WORKING
            self.stdout.write(self.style.SUCCESS("✔ Constraint Check: Duplicate Student correctly blocked."))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"✘ Unexpected Error during constraint check: {e}"))

    def test_faculty_operations(self, college, faculty):
        c = Client()
        self.stdout.write(self.style.WARNING("--- STARTING FACULTY OPERATIONS TEST ---"))

        # 1. LOGIN & GET TOKEN
        login_payload = {'email': 'faculty@test.edu', 'password': 'FacultyPass123'}
        try:
            response = c.post(reverse('psapp:jwt_login'), login_payload, content_type='application/json')
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"✘ Login URL Crashed: {e}"))
            return

        if response.status_code != 200:
            self.stdout.write(self.style.ERROR(f"✘ Login failed ({response.status_code}). Cannot proceed."))
            return

        # Extract Token
        try:
            json_response = response.json()
            
            # THE FIX: Look for 'access_token' specifically
            token = json_response.get('access_token') 

            if not token:
                self.stdout.write(self.style.ERROR(f"✘ Login worked but key 'access_token' missing. Got: {json_response.keys()}"))
                return

            auth_headers = {'HTTP_AUTHORIZATION': f'Bearer {token}'}
            self.stdout.write(self.style.SUCCESS("✔ Token acquired."))
        except Exception as e:
             self.stdout.write(self.style.ERROR(f"✘ Failed to parse Token: {e}"))
             return

        # 2. CREATE A CLASS
        dept = Department.objects.get(college=college)
        create_class_data = {
            'department_id': dept.id,
            'class_name': 'B.Tech IT',
            'section': 'A',
            'academic_year': '2024-2028',
            'current_year': 2,
            'current_semester': 4
        }

        try:
            resp = c.post(
                reverse('psapp:create_class_api'), 
                create_class_data, 
                content_type='application/json',
                **auth_headers 
            )
            
            if resp.status_code in [200, 201]:
                self.stdout.write(self.style.SUCCESS(f"✔ API Check: Create Class Success (ID: {resp.json().get('id')})"))
            else:
                self.stdout.write(self.style.ERROR(f"✘ API Check: Create Class Failed ({resp.status_code}) - {resp.content}"))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"✘ API Check: Create Class Crashed - {e}"))

        # 3. GET DASHBOARD DATA
        try:
            resp = c.get(reverse('psapp:get_dashboard_data'), **auth_headers)
            if resp.status_code == 200:
                self.stdout.write(self.style.SUCCESS("✔ API Check: Dashboard Data Fetch Success"))
            else:
                self.stdout.write(self.style.ERROR(f"✘ API Check: Dashboard Data Failed ({resp.status_code})"))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"✘ API Check: Dashboard Crashed - {e}"))
        c = Client()
        self.stdout.write(self.style.WARNING("--- STARTING FACULTY OPERATIONS TEST ---"))

        # 1. LOGIN & GET TOKEN
        login_payload = {'email': 'faculty@test.edu', 'password': 'FacultyPass123'}
        try:
            response = c.post(reverse('psapp:jwt_login'), login_payload, content_type='application/json')
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"✘ Login URL Crashed: {e}"))
            return

        if response.status_code != 200:
            self.stdout.write(self.style.ERROR(f"✘ Login failed ({response.status_code}). Cannot proceed."))
            return


        try:
            json_response = response.json()
            
            # 🔍 DEBUG: Print the actual response to see the key name
            self.stdout.write(self.style.WARNING(f"🔍 DEBUG RESPONSE: {json_response}"))

            # Try to find the token using common keys
            token = json_response.get('access') or json_response.get('token') or json_response.get('key')
            
            if not token:
                # Check if it's nested (e.g., {'data': {'token': ...}})
                if 'data' in json_response and 'token' in json_response['data']:
                    token = json_response['data']['token']

            if not token:
                self.stdout.write(self.style.ERROR("✘ Login worked but returned no Token."))
                return

            auth_headers = {'HTTP_AUTHORIZATION': f'Bearer {token}'}
            self.stdout.write(self.style.SUCCESS("✔ Token acquired."))
        except Exception as e:
             self.stdout.write(self.style.ERROR(f"✘ Failed to parse Token: {e}"))
             return
        except:
             self.stdout.write(self.style.ERROR("✘ Failed to parse Token from response."))
             return

        # 2. CREATE A CLASS
        dept = Department.objects.get(college=college)
        create_class_data = {
            'department_id': dept.id,
            'class_name': 'B.Tech IT',
            'section': 'A',
            'academic_year': '2024-2028',
            'current_year': 2,
            'current_semester': 4
        }

        try:
            resp = c.post(
                reverse('psapp:create_class_api'), 
                create_class_data, 
                content_type='application/json',
                **auth_headers 
            )
            
            if resp.status_code in [200, 201]:
                self.stdout.write(self.style.SUCCESS(f"✔ API Check: Create Class Success (ID: {resp.json().get('id')})"))
            else:
                self.stdout.write(self.style.ERROR(f"✘ API Check: Create Class Failed ({resp.status_code}) - {resp.content}"))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"✘ API Check: Create Class Crashed - {e}"))

        # 3. GET DASHBOARD DATA
        try:
            resp = c.get(reverse('psapp:get_dashboard_data'), **auth_headers)
            if resp.status_code == 200:
                self.stdout.write(self.style.SUCCESS("✔ API Check: Dashboard Data Fetch Success"))
            else:
                self.stdout.write(self.style.ERROR(f"✘ API Check: Dashboard Data Failed ({resp.status_code})"))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"✘ API Check: Dashboard Crashed - {e}"))