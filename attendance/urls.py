from django.urls import path
from . import views

app_name = "attendance"

urlpatterns = [
    # Student
    path("", views.dashboard, name="dashboard"),
    path("history/", views.student_history, name="history"),

    # AJAX endpoints
    path("generate-code/", views.generate_code, name="generate_code"),
    path("submit-attendance/", views.submit_attendance, name="submit_attendance"),

    # Lecturer
    path("lecturer/", views.lecturer_dashboard, name="lecturer_dashboard"),
    path("lecturer/export/<int:session_id>/", views.export_attendance_csv, name="export_csv"),
     
    path("register/", views.register, name="register"),
    
    # Admin Dashboard & Reports
    path("admin-dashboard/", views.admin_dashboard, name="admin_dashboard"),
    path("student-report/", views.student_attendance_report, name="student_report"),
    path("student-report/<int:student_id>/", views.student_attendance_report, name="student_detail"),
    path("export-level/<int:level_id>/", views.export_level_attendance, name="export_level"),
    path("attendance-trends/", views.attendance_trends, name="attendance_trends"),
    path("bulk-import/", views.bulk_student_import, name="bulk_import"),
    
    # Semester Management
    path("semesters/", views.semester_list, name="semester_list"),
    path("semester/archive/<int:semester_id>/", views.archive_semester, name="archive_semester"),
    path("semester/activate/<int:semester_id>/", views.activate_semester, name="activate_semester"),
    
    # Student CSV Export (only CSV, no PDF)
    path("export/my-csv/", views.export_my_attendance_csv, name="export_my_csv"),
    
    # Admin CSV Export (only CSV, no PDF)
    path("admin/export/student/<int:student_id>/csv/", views.admin_export_student_csv, name="admin_export_student_csv"),
    path("admin/export/all/csv/", views.admin_export_all_students_csv, name="admin_export_all_csv"),
    path("admin/export/level/<int:level_id>/csv/", views.admin_export_all_students_csv, name="admin_export_level_csv"),
    path("admin/search/", views.admin_search_students, name="admin_search"),
]