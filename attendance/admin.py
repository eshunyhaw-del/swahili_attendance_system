from django.contrib import admin
from .models import Level, Semester, Course, ClassSession, UserProfile, AttendanceCode, AttendanceRecord

@admin.register(Level)
class LevelAdmin(admin.ModelAdmin):
    list_display = ('name',)
    search_fields = ('name',)

@admin.register(Semester)
class SemesterAdmin(admin.ModelAdmin):
    list_display = ('name', 'year', 'start_date', 'end_date', 'is_active')
    list_filter = ('year', 'is_active')
    search_fields = ('name',)

@admin.register(Course)
class CourseAdmin(admin.ModelAdmin):
    list_display = ('code', 'name', 'level', 'semester')
    list_filter = ('level', 'semester')
    search_fields = ('code', 'name')

@admin.register(ClassSession)
class ClassSessionAdmin(admin.ModelAdmin):
    list_display = ('course', 'date', 'topic', 'lecturer')
    list_filter = ('course', 'date')
    search_fields = ('topic',)

@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'level', 'student_id_number')
    list_filter = ('level',)
    search_fields = ('user__username', 'student_id_number')

@admin.register(AttendanceCode)
class AttendanceCodeAdmin(admin.ModelAdmin):
    list_display = ('code_string', 'student', 'class_session', 'generated_at', 'expires_at', 'used_at')
    list_filter = ('class_session__course',)
    search_fields = ('code_string', 'student__username')
    readonly_fields = ('generated_at',)

@admin.register(AttendanceRecord)
class AttendanceRecordAdmin(admin.ModelAdmin):
    list_display = ('student', 'class_session', 'submitted_at')
    list_filter = ('class_session__course',)
    search_fields = ('student__username',)