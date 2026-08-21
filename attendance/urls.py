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
    path("course/deregister/", views.student_deregister_course, name="student_deregister_course"),
    path("course/staff-deregister/", views.staff_deregister_course, name="staff_deregister_course"),
    path("course/staff-reactivate/", views.staff_reactivate_course, name="staff_reactivate_course"),
    path("support/", views.support, name="support"),
    path("export/my-csv/", views.export_my_attendance_csv, name="export_my_csv"),
    path("student-guide/", views.student_guide, name="student_guide"),
    
    # Email Verification (legacy link-based)
    path("verify-email/<str:token>/", views.verify_email, name="verify_email"),

    # Magic-link flows (one-tap email verification)
    path("magic/verify/<uuid:token>/", views.magic_verify_registration, name="magic_verify_registration"),
    path("magic/reset/<uuid:token>/", views.magic_reset_password, name="magic_reset_password"),

    # OTP flows
    path("otp/registration/verify/", views.otp_verify_registration, name="otp_verify_registration"),
    path("otp/resend-verification/", views.resend_verification, name="resend_verification"),
    path("otp/login/verify/", views.otp_verify_login, name="otp_verify_login"),
    path("otp/password-reset/", views.otp_password_reset_request, name="otp_password_reset"),
    path("otp/password-reset/verify/", views.otp_verify_password_reset, name="otp_verify_password_reset"),
    path("otp/password-reset/set-password/", views.otp_set_password, name="otp_set_password"),
    
    # AJAX endpoints
    path("submit-ta-code/", views.student_submit_ta_code, name="student_submit_ta_code"),
    path("ta/get-students-ajax/", views.ta_get_students_ajax, name="ta_get_students_ajax"),
    
    # Lecturer
    path("lecturer/", views.lecturer_dashboard, name="lecturer_dashboard"),
    path("lecturer/export/<int:session_id>/", views.export_attendance_csv, name="export_csv"),
    
    # TA
    path("ta/dashboard/", views.ta_dashboard, name="ta_dashboard"),
    path("ta/history/", views.ta_history, name="ta_history"),
    path("ta/add-levels/", views.ta_add_levels, name="ta_add_levels"),
    path("ta/announcements/", views.ta_announcements, name="ta_announcements"),
    path("ta/guide/", views.ta_guide, name="ta_guide"),
    path("ta/change-password/", views.ta_change_password, name="ta_change_password"),
    path("ta/export/session/<int:session_id>/", views.ta_export_session_csv, name="ta_export_session_csv"),
    path("ta/generate-code/", views.ta_generate_code, name="ta_generate_code"),
    path("ta/mark-distributed/<int:code_id>/", views.ta_mark_distributed, name="ta_mark_distributed"),
    path("ta/generate-all-codes/", views.ta_generate_all_codes, name="ta_generate_all_codes"),
    path("ta/support/", views.ta_support_tickets, name="ta_support"),
    path("ta/announcements/<int:ann_id>/delete/", views.ta_delete_announcement, name="ta_delete_announcement"),
    path("ta/announcements/<int:ann_id>/edit/", views.ta_edit_announcement, name="ta_edit_announcement"),
    path("notifications/mark-read/", views.mark_notifications_read, name="mark_notifications_read"),
    path("notifications/", views.notifications_page, name="notifications"),
    path("notifications/ann/mark-read/<int:notif_id>/", views.student_mark_notification_read, name="student_mark_notification_read"),
    path("notifications/ann/mark-all-read/", views.student_mark_all_notifications_read, name="student_mark_all_read"),
    path("notifications/unread-count/", views.notification_unread_count, name="notification_unread_count"),
    path("notifications/sys/mark-read/<int:notif_id>/", views.system_mark_notification_read, name="system_mark_notification_read"),
    path("notifications/sys/mark-all-read/", views.system_mark_all_notifications_read, name="system_mark_all_read"),
    
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

    # Community
    path("community/events/", views.community_events, name="community_events"),
    path("community/executives/", views.community_executives, name="community_executives"),
    path("community/alumni/", views.community_alumni, name="community_alumni"),
    path("community/clubs/", views.community_clubs, name="community_clubs"),
    path("community/dues/", views.community_dues, name="community_dues"),
]