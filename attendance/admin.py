from django.contrib import admin
from .models import (
    Level, Semester, Course, ClassSession, UserProfile, 
    TAProfile, TACode, AttendanceCode, AttendanceRecord, 
    SupportTicket, CodeMisuseAlert
)


@admin.register(Level)
class LevelAdmin(admin.ModelAdmin):
    list_display = ('name',)
    search_fields = ('name',)


@admin.register(Semester)
class SemesterAdmin(admin.ModelAdmin):
    list_display = ('name', 'year', 'start_date', 'end_date', 'is_active', 'is_archived')
    list_filter = ('year', 'is_active', 'is_archived')
    search_fields = ('name',)


@admin.register(Course)
class CourseAdmin(admin.ModelAdmin):
    list_display = ('code', 'name', 'level', 'semester')
    list_filter = ('level', 'semester')
    search_fields = ('code', 'name')


@admin.register(ClassSession)
class ClassSessionAdmin(admin.ModelAdmin):
    list_display = ('course', 'date', 'start_time', 'end_time', 'topic', 'lecturer')
    list_filter = ('course', 'date')
    search_fields = ('topic',)


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'level', 'student_id_number', 'student_email', 'email_verified')
    list_filter = ('level', 'email_verified')
    search_fields = ('user__username', 'student_id_number', 'student_email')
    readonly_fields = ('email_verification_token', 'verification_sent_at')


@admin.register(TAProfile)
class TAProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'phone_number', 'is_approved', 'is_active', 'approved_at')
    list_filter = ('is_approved', 'is_active', 'assigned_levels')
    search_fields = ('user__username', 'user__email', 'phone_number')
    readonly_fields = ('approved_at',)
    filter_horizontal = ('assigned_levels', 'assigned_courses')
    
    fieldsets = (
        ('User Information', {
            'fields': ('user', 'phone_number')
        }),
        ('Assigned Levels & Courses', {
            'fields': ('assigned_levels', 'assigned_courses')
        }),
        ('Approval Status', {
            'fields': ('is_approved', 'approved_by', 'approved_at', 'approval_notes')
        }),
        ('Account Status', {
            'fields': ('is_active',)
        }),
    )
    
    actions = ['approve_selected_tas']
    
    def approve_selected_tas(self, request, queryset):
        from django.utils import timezone
        updated = queryset.update(is_approved=True, approved_by=request.user, approved_at=timezone.now())
        self.message_user(request, f'{updated} TA(s) approved successfully.')
    approve_selected_tas.short_description = "Approve selected TAs"


@admin.register(TACode)
class TACodeAdmin(admin.ModelAdmin):
    list_display = ('code', 'student', 'class_session', 'ta', 'is_used', 'is_distributed', 'generated_at')
    list_filter = ('is_used', 'is_distributed', 'class_session__course')
    search_fields = ('code', 'student__username', 'ta__username')


@admin.register(AttendanceCode)
class AttendanceCodeAdmin(admin.ModelAdmin):
    list_display = ('code_string', 'student', 'class_session', 'generated_at', 'expires_at', 'used_at')
    list_filter = ('class_session__course',)
    search_fields = ('code_string', 'student__username')
    readonly_fields = ('generated_at',)


@admin.register(AttendanceRecord)
class AttendanceRecordAdmin(admin.ModelAdmin):
    list_display = ('student', 'class_session', 'submitted_at', 'ip_address', 'status')
    list_filter = ('class_session__course', 'status')
    search_fields = ('student__username',)


@admin.register(SupportTicket)
class SupportTicketAdmin(admin.ModelAdmin):
    list_display = ('subject', 'student', 'status', 'created_at')
    list_filter = ('status',)
    search_fields = ('subject', 'student__username', 'message')


@admin.register(CodeMisuseAlert)
class CodeMisuseAlertAdmin(admin.ModelAdmin):
    list_display = ('code', 'attempted_by', 'attempted_at', 'is_resolved')
    list_filter = ('is_resolved',)
    search_fields = ('code__code_string', 'attempted_by__username')