from django.urls import path
from . import views

app_name = "attendance"

urlpatterns = [
    # Student
    path("", views.dashboard, name="dashboard"),
    path("change-password/", views.change_password, name="change_password"),
    path("history/", views.student_history, name="history"),
    path("register/", views.register, name="register"),
    path("ta-register/", views.ta_register, name="ta_register"),
    path("course-registration/", views.course_registration, name="course_registration"),
    path("support/", views.support, name="support"),
    path("export/my-csv/", views.export_my_attendance_csv, name="export_my_csv"),
    path("student-guide/", views.student_guide, name="student_guide"),
    
    # Email Verification
    path("verify-email/<str:token>/", views.verify_email, name="verify_email"),
    
    # AJAX endpoints
    path("generate-code/", views.generate_code, name="generate_code"),
    path("submit-attendance/", views.submit_attendance, name="submit_attendance"),
    path("submit-ta-code/", views.student_submit_ta_code, name="student_submit_ta_code"),
    path("ta/get-students-ajax/", views.ta_get_students_ajax, name="ta_get_students_ajax"),
    
    # Lecturer
    path("lecturer/", views.lecturer_dashboard, name="lecturer_dashboard"),
    path("lecturer/export/<int:session_id>/", views.export_attendance_csv, name="export_csv"),
    
    # TA
    path("ta/dashboard/", views.ta_dashboard, name="ta_dashboard"),
    path("ta/generate-code/", views.ta_generate_code, name="ta_generate_code"),
    path("ta/mark-distributed/<int:code_id>/", views.ta_mark_distributed, name="ta_mark_distributed"),
    path("ta/generate-all-codes/", views.ta_generate_all_codes, name="ta_generate_all_codes"),
    
    # Admin
    path("dashboard-admin/", views.admin_dashboard, name="admin_dashboard"),
    path("dashboard-admin/search/", views.admin_search_students, name="admin_search"),
    path("dashboard-admin/support/", views.admin_support_tickets, name="admin_support"),
    path("dashboard-admin/alerts/", views.admin_alerts, name="admin_alerts"),
    path("dashboard-admin/export/student/<int:student_id>/csv/", views.admin_export_student_csv, name="admin_export_student_csv"),
    path("dashboard-admin/export/all/csv/", views.admin_export_all_students_csv, name="admin_export_all_csv"),
    path("admin/pending-tas/", views.pending_tas, name="pending_tas"),
    path("export-level/<int:level_id>/", views.export_level_attendance, name="export_level"),
    path("student-report/", views.student_attendance_report, name="student_report"),
]