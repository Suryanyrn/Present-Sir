from django.urls import path
from psapp.views import (
    auth_views,
    faculty_views,
    college_auth,
    college_core,
    college_faculty,
    course_views,
    timetable_views,
    report_views,
    semester_views,
    student_views
)

app_name = 'psapp'

urlpatterns = [
    # --- Common / Landing ---
    path('', auth_views.index_view, name='index'),

    # ==========================================
    # GROUP 1: FACULTY & COMMON AUTHENTICATION
    # ==========================================
    path("login/", auth_views.login, name="login"),
    path("register/", auth_views.register, name="register"),
    path('logout/', auth_views.logout_view, name='logout'),
    
    # JWT & OTP
    path("api/jwt/login/", auth_views.jwt_login_api, name="jwt_login"),
    path("api/jwt/refresh/", auth_views.jwt_refresh_api, name="jwt_refresh"),
    path("send-otp/", auth_views.send_otp, name="send_otp"),
    path("verify-email-otp/", auth_views.verify_email_otp, name="verify_email_otp"),
    path("forgot-send-otp/", auth_views.forgot_send_otp, name="forgot_send_otp"),
    path("forgot-verify-otp/", auth_views.forgot_verify_otp, name="forgot_verify_otp"),
    path("reset-password/", auth_views.reset_password, name="reset_password"),

    # ==========================================
    # GROUP 2: FACULTY DASHBOARD & OPERATIONS
    # ==========================================
    path("dashboard/", faculty_views.dashboard_template, name="dashboard"),
    path("api/get-dashboard-data/", faculty_views.get_dashboard_data, name="get_dashboard_data"),
    path('api/edit-profile/', faculty_views.edit_profile_api, name='edit_profile_api'),
    
    # Class & Student Management (Faculty Side)
    path("api/create-class/", faculty_views.create_class_api, name="create_class_api"),
    path('api/delete-class/<int:course_id>/', faculty_views.delete_class_api, name='delete_class_api'),
    path('api/copy-class/', faculty_views.copy_class_api, name='copy_class_api'),
    path('api/edit-student/', faculty_views.edit_student_api, name='edit_student_api'),
    path('api/student-stats/<int:student_id>/', faculty_views.get_student_stats_api, name='get_student_stats_api'),
    
    # Attendance Operations
    path("api/save-attendance/", faculty_views.save_attendance_api, name="save_attendance_api"),
    path('api/update-attendance/', faculty_views.update_attendance_api, name='update_attendance'),
    path('api/defaulters/<int:course_id>/', faculty_views.get_defaulters_list, name='get_defaulters_list'),
    path('api/leaderboard/<int:course_id>/', faculty_views.get_leaderboard_api, name='get_leaderboard'),
    path('api/send-warnings/', faculty_views.send_warning_emails_api, name='send_warning_emails'),

    # Faculty Notifications & Requests
    path('api/get-requests/', faculty_views.get_faculty_requests_api, name='get_faculty_requests'),
    path('api/respond-request/', faculty_views.respond_faculty_request_api, name='respond_faculty_request'),
    path('api/get-notifications/', faculty_views.get_faculty_notifications_api, name='get_faculty_notifs'),
    path('api/mark-notif-read/', faculty_views.mark_faculty_notif_read, name='mark_faculty_notif_read'),

    # ==========================================
    # GROUP 3: COLLEGE ADMIN AUTHENTICATION
    # ==========================================
    path('college/login/', college_auth.college_login_view, name='college_login'),
    path('college/login-api/', college_auth.college_login_api, name='college_login_api'),
    path('college/register-api/', college_auth.college_register_api, name='college_register_api'),
    path('college/forgot-otp/', college_auth.college_forgot_otp, name='college_forgot_otp'),
    path('college/forgot-verify/', college_auth.college_forgot_verify, name='college_forgot_verify'),
    path('college/reset-pass/', college_auth.college_reset_pass, name='college_reset_pass'),
    path('college/logout/', college_auth.college_logout_view, name='college_logout'),

    # ==========================================
    # GROUP 4: COLLEGE CORE (Depts, Classes, Students)
    # ==========================================
    path('college/dashboard/', college_core.college_dashboard_view, name='college_dashboard'),
    path('college/get-data/', college_core.get_college_dashboard_data, name='get_college_data'),
    path('college/notifications/', college_core.get_college_notifications_api, name='get_notifications'),
    path('college/mark-read/', college_core.mark_notification_read_api, name='mark_read'),

    # Structure Management
    path('college/add-department/', college_core.add_department_api, name='add_department'),
    path('college/add-class/', college_core.add_academic_class_api, name='add_class'),
    path('college/add-student/', college_core.add_student_to_class_api, name='add_student_admin'),
    path('college/add-single-student/', college_core.add_student_to_existing_class_api, name='add_student_to_existing_class_api'),
    path('college/delete-student/', college_core.delete_student_api, name='delete_student_api'),
    path('college/get-class-students/', college_core.get_class_students_api, name='get_class_students'),
    path('college/get-class-students-all/', college_core.get_class_students_admin_all, name='get_class_students_admin_all'),
    path('college/student-profile/<int:student_id>/', college_core.get_admin_student_profile, name='get_admin_student_profile'),

    # ==========================================
    # GROUP 5: COLLEGE FACULTY MANAGEMENT
    # ==========================================
    path('college/search-faculty/', college_faculty.search_faculty_api, name='search_faculty'),
    path('college/search-faculty-id/', college_faculty.search_faculty_by_id_api, name='search_faculty_id'),
    path('college/get-faculty-details/', college_faculty.get_faculty_details_admin, name='get_faculty_details_admin'),
    path('college/assign-faculty/', college_faculty.assign_faculty_api, name='assign_faculty'),
    path('college/send-invite/', college_faculty.send_faculty_invite_api, name='send_invite'),
    path('college/terminate-faculty/', college_faculty.terminate_faculty_api, name='terminate_faculty_api'),

    # ==========================================
    # GROUP 6: COURSE/SUBJECT MANAGEMENT
    # ==========================================
    path('college/add-course/', course_views.add_dept_course_api, name='add_course'),
    path('college/get-courses/', course_views.get_dept_courses_api, name='get_courses'),
    path('college/edit-course/', course_views.edit_dept_course_api, name='edit_course'),
    path('college/delete-course/', course_views.delete_dept_course_api, name='delete_course'),
    path('college/get-courses-for-export/', course_views.get_class_assigned_courses_for_export_api, name='get_courses_for_export'),
    
    # Assignments
    path('college/assign-course/', course_views.assign_subject_to_class_api, name='assign_course'),
    path('college/assign-special-course-api/', course_views.assign_special_course_api, name='assign_special_course_api'),
    path('college/revoke-course/', course_views.revoke_course_api, name='revoke_course'),
    path('college/get-class-courses/', course_views.get_class_assigned_courses_api, name='get_class_courses'),

    # ==========================================
    # GROUP 7: TIMETABLE MANAGEMENT
    # ==========================================
    path('college/timetable/init/', timetable_views.init_timetable_api, name='init_timetable'),
    path('college/timetable/save-slot/', timetable_views.save_timetable_slot_api, name='save_timetable_slot'),
    path('college/timetable/check-conflict/', timetable_views.check_faculty_conflict_api, name='check_conflict'),
    path('college/timetable/save-config/', timetable_views.save_timetable_settings_api, name='save_timetable_config'),
    path('college/get-suggested-session', timetable_views.get_suggested_session_api, name='get_suggested_session'),

    # ==========================================
    # GROUP 8: REPORTS & ANALYTICS
    # ==========================================
    path("export/csv/<int:course_id>/", report_views.export_attendance_csv, name="export_attendance_csv"),
    path('college/class-analytics/', report_views.get_class_analytics_api, name='get_class_analytics'),
    path('export-admin-course-report/<int:course_id>/', report_views.export_admin_course_report, name='export_admin_course_report'),
    path('export-admin-class-overall-report/<int:class_id>/', report_views.export_admin_class_overall_report, name='export_admin_class_overall_report'),
    path('college/export-deleted-students/<int:class_id>/', report_views.export_deleted_students_csv, name='export_deleted_students_csv'),
    path('college/get-deleted-students/', report_views.get_deleted_students_api, name='get_deleted_students_api'),
    path('api/get-class-report-card/', report_views.get_class_report_card_api, name='get_class_report_card_api'),
    path('api/class-history/', report_views.get_class_history_api, name='get_class_history_api'),

    # ==========================================
    # GROUP 9: SEMESTER & SENSITIVE OPS
    # ==========================================
    # Action OTPs & Delete Operations
    path('college/send-delete-otp/', semester_views.send_delete_otp_api, name='send_delete_otp_api'),
    path('college/verify-delete-otp/', semester_views.verify_delete_otp_api, name='verify_delete_otp_api'),
    path('college/delete-department/', semester_views.delete_department_api, name='delete_department_api'),
    path('college/delete-class-admin/', semester_views.delete_class_admin_api, name='delete_class_admin_api'),
    path('college/send-action-otp', semester_views.send_action_otp_api, name='send_action_otp_api'),
    path('college/verify-action-and-execute-api', semester_views.verify_action_and_execute_api, name='verify_action_and_execute_api'),
    path('college/send-add-dept-otp/', semester_views.send_add_dept_otp_api, name='send_add_dept_otp'),
    path('college/verify-add-dept-otp/', semester_views.verify_add_dept_otp_api, name='verify_add_dept_otp'),

    # Semester Cycles
    path('college/sem/start/send-otp/', semester_views.send_start_sem_otp, name='send_start_sem_otp'),
    path('college/sem/start/verify/', semester_views.verify_start_sem_api, name='verify_start_sem_api'),
    path('college/sem/end/send-otp/', semester_views.send_end_sem_otp, name='send_end_sem_otp'),
    path('college/sem/end/execute/', semester_views.execute_end_semester, name='end_semester_api'),
    path('api/archive-class/', semester_views.archive_class_api, name='archive_class_api'),

    # ==========================================
    # GROUP 10: STUDENT PORTAL & PUBLIC
    # ==========================================
    path('student/portal/', student_views.student_portal_view, name='student_portal'),
    path('api/public/get-depts/', student_views.public_get_college_depts, name='public_get_college_depts'),
    path('api/public/get-profile/', student_views.public_get_student_profile, name='public_get_student_profile'),
    path('api/get-dept-students/', course_views.get_dept_students_for_selection_api, name='get_dept_students'),
    # Resignation
    path('api/send-resign-otp/', student_views.send_resign_otp, name='send_resign_otp'),
    path('api/leave-college/', student_views.leave_college_api, name='leave_college_api'),
]