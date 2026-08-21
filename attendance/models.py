import random
import string
import uuid
from datetime import timedelta, datetime
from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone


class Level(models.Model):
    name = models.CharField(max_length=10, unique=True)

    def __str__(self):
        return f"Level {self.name}"


class Semester(models.Model):
    name = models.CharField(max_length=50)
    year = models.IntegerField()
    start_date = models.DateField()
    end_date = models.DateField()
    is_active = models.BooleanField(default=False)
    is_archived = models.BooleanField(default=False)

    def __str__(self):
        status = " (Archived)" if self.is_archived else " (Active)" if self.is_active else ""
        return f"{self.name} {self.year}{status}"


class Course(models.Model):
    code = models.CharField(max_length=20, unique=True)
    name = models.CharField(max_length=100)
    level = models.ForeignKey(Level, on_delete=models.CASCADE)
    semester = models.ForeignKey(Semester, on_delete=models.CASCADE)

    def __str__(self):
        return f"{self.code} - {self.name}"


class ClassSession(models.Model):
    course = models.ForeignKey(Course, on_delete=models.CASCADE)
    date = models.DateField()
    start_time = models.TimeField(default='07:30', help_text="Class start time (e.g., 07:30)")
    end_time = models.TimeField(default='09:20', help_text="Class end time (e.g., 09:20)")
    topic = models.CharField(max_length=200)
    lecturer = models.ForeignKey(User, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.course} on {self.date} ({self.start_time} - {self.end_time})"
    
    def is_active_now(self):
        """Check if class is currently active (within time window)"""
        now = timezone.now()
        today = now.date()
        current_time = now.time()
        
        if self.date == today:
            return self.start_time <= current_time <= self.end_time
        return False


class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    level = models.ForeignKey(Level, on_delete=models.SET_NULL, null=True, blank=True)
    student_id_number = models.CharField(max_length=50, unique=True, blank=True, null=True)
    student_email = models.EmailField(blank=True, null=True)
    registered_courses = models.ManyToManyField(Course, blank=True, related_name='registered_students', through='CourseRegistration')
    
    # Email Verification Fields
    email_verified = models.BooleanField(default=False)
    email_verification_token = models.CharField(max_length=100, blank=True, null=True)
    verification_sent_at = models.DateTimeField(blank=True, null=True)

    must_change_password = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.user.username} - Level {self.level}"


class CourseRegistration(models.Model):
    """Explicit through-model for UserProfile.registered_courses.

    Each row is one student's registration in one course. Deregistration is a
    soft state change (is_active=False) — rows are NEVER deleted, so the full
    history of who dropped a course and when is preserved for auditing.
    """
    user_profile = models.ForeignKey(
        UserProfile, on_delete=models.CASCADE, related_name='course_registrations'
    )
    course = models.ForeignKey(
        Course, on_delete=models.CASCADE, related_name='course_registrations'
    )
    is_active = models.BooleanField(default=True)
    registered_at = models.DateTimeField(auto_now_add=True)
    deregistered_at = models.DateTimeField(null=True, blank=True)
    deregistered_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='deregistrations',
        help_text="User (student, TA, or admin) who performed the deregistration",
    )

    class Meta:
        unique_together = ('user_profile', 'course')

    def __str__(self):
        state = "active" if self.is_active else "inactive"
        return f"{self.user_profile.user.username} → {self.course.code} ({state})"


class TAProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    assigned_levels = models.ManyToManyField(Level, blank=True, help_text="Which levels this TA handles")
    assigned_courses = models.ManyToManyField(Course, blank=True, help_text="Specific courses this TA handles")
    phone_number = models.CharField(max_length=15, blank=True, null=True)
    is_active = models.BooleanField(default=True)
    
    # TA Approval Fields
    is_approved = models.BooleanField(default=False)
    approved_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='approved_tas')
    approved_at = models.DateTimeField(blank=True, null=True)
    approval_notes = models.TextField(blank=True, null=True)

    def __str__(self):
        levels = ', '.join([l.name for l in self.assigned_levels.all()])
        status = "✓ Approved" if self.is_approved else "⏳ Pending Approval"
        return f"TA: {self.user.username} - Levels: {levels} - {status}"


class TACode(models.Model):
    """Code generated by TA for a specific student and session"""
    code = models.CharField(max_length=6)
    student = models.ForeignKey(User, on_delete=models.CASCADE, related_name='ta_codes')
    class_session = models.ForeignKey(ClassSession, on_delete=models.CASCADE)
    ta = models.ForeignKey(User, on_delete=models.CASCADE, related_name='generated_codes')
    generated_at = models.DateTimeField(auto_now_add=True)
    used_at = models.DateTimeField(null=True, blank=True)
    is_used = models.BooleanField(default=False)
    is_distributed = models.BooleanField(default=False)
    distributed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        unique_together = ['code', 'class_session']

    def __str__(self):
        status = "Used" if self.is_used else "Pending"
        return f"Code {self.code} for {self.student.username} - {status}"


class AttendanceCode(models.Model):
    code_string = models.CharField(max_length=20, unique=True, blank=True)
    student = models.ForeignKey(User, on_delete=models.CASCADE, related_name='codes')
    class_session = models.ForeignKey(ClassSession, on_delete=models.CASCADE)
    generated_at = models.DateTimeField(default=timezone.now)
    expires_at = models.DateTimeField(null=True, blank=True)
    used_at = models.DateTimeField(null=True, blank=True)
    is_valid = models.BooleanField(default=True)

    def save(self, *args, **kwargs):
        if not self.code_string:
            self.code_string = ''.join(random.choices(
                string.ascii_uppercase + string.digits, k=8
            ))
        
        if not self.expires_at:
            session_date = self.class_session.date
            expiry_datetime = datetime.combine(session_date, datetime.max.time()) + timedelta(days=7)
            self.expires_at = timezone.make_aware(expiry_datetime)
        
        super().save(*args, **kwargs)

    def can_use(self):
        if self.used_at:
            return False, "Code already used"
        if self.is_expired():
            return False, "Code has expired"
        if not self.is_valid:
            return False, "Code is invalid"
        return True, "OK"

    def is_expired(self):
        return timezone.now() > self.expires_at

    def __str__(self):
        code = self.code_string or 'N/A'
        student = self.student.username if self.student else 'Unknown'
        session = str(self.class_session) if self.class_session else 'Unknown'
        return f"{code} — {student} — {session}"


class AttendanceRecord(models.Model):
    student = models.ForeignKey(User, on_delete=models.CASCADE, related_name='attendance')
    class_session = models.ForeignKey(ClassSession, on_delete=models.CASCADE)
    code = models.OneToOneField(AttendanceCode, on_delete=models.CASCADE)
    submitted_at = models.DateTimeField(auto_now_add=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True, null=True)
    status = models.CharField(max_length=20, default='on_time')

    def __str__(self):
        return f"{self.student.username} attended {self.class_session}"


class SupportTicket(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('in_progress', 'In Progress'),
        ('resolved', 'Resolved'),
        ('closed', 'Closed'),
    ]
    
    student = models.ForeignKey(User, on_delete=models.CASCADE, related_name='support_tickets')
    subject = models.CharField(max_length=200)
    message = models.TextField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    admin_response = models.TextField(blank=True, null=True)
    assigned_ta = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='assigned_tickets')

    def __str__(self):
        return f"{self.subject} - {self.student.username}"


class Notification(models.Model):
    recipient = models.ForeignKey(User, on_delete=models.CASCADE, related_name='notifications')
    message = models.CharField(max_length=300)
    link = models.CharField(max_length=200, blank=True)
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Notif → {self.recipient.username}: {self.message[:60]}"


class CodeMisuseAlert(models.Model):
    code = models.ForeignKey(AttendanceCode, on_delete=models.SET_NULL, null=True, blank=True)
    attempted_by = models.ForeignKey(User, on_delete=models.CASCADE)
    attempted_at = models.DateTimeField(auto_now_add=True)
    reason = models.CharField(max_length=200)
    is_resolved = models.BooleanField(default=False)

    def __str__(self):
        code = self.code.code_string if self.code else 'N/A'
        return f"Misuse alert: {code} by {self.attempted_by.username}"


class TAnnouncement(models.Model):
    """Announcement sent by a TA to all students registered in a specific course."""
    ta = models.ForeignKey(User, on_delete=models.CASCADE, related_name='sent_announcements')
    title = models.CharField(max_length=200)
    message = models.TextField()
    sent_at = models.DateTimeField(auto_now_add=True)
    course = models.ForeignKey('Course', on_delete=models.SET_NULL, null=True, blank=True, related_name='announcements')
    target_levels = models.ManyToManyField(Level, blank=True)
    recipient_count = models.IntegerField(default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['-sent_at']

    def __str__(self):
        return f"Announcement: {self.title} by {self.ta.get_full_name()}"


class StudentNotification(models.Model):
    """Per-student notification record created when a TA sends an announcement."""
    student = models.ForeignKey(User, on_delete=models.CASCADE, related_name='announcement_notifications')
    announcement = models.ForeignKey(TAnnouncement, on_delete=models.CASCADE, related_name='student_notifications')
    is_read = models.BooleanField(default=False)
    read_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-announcement__sent_at']

    def __str__(self):
        return f"Notif → {self.student.username}: {self.announcement.title[:50]}"


class CulturalDate(models.Model):
    """A recurring cultural / language celebration date (day + month, no year)."""
    name = models.CharField(max_length=200)
    description = models.TextField()
    day = models.IntegerField()
    month = models.IntegerField()
    emoji = models.CharField(max_length=10, default='🌍')
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['month', 'day']
        indexes = [
            models.Index(fields=['day', 'month', 'is_active'], name='att_cultdate_day_month_idx'),
        ]

    def __str__(self):
        return f"{self.emoji} {self.name} ({self.day}/{self.month})"


class SystemNotification(models.Model):
    """System-wide notification (e.g. cultural date celebration) sent to a specific user."""
    TYPE_CULTURAL = 'cultural_date'
    TYPE_SYSTEM   = 'system'
    TYPE_CHOICES  = [
        (TYPE_CULTURAL, 'Cultural Date'),
        (TYPE_SYSTEM,   'System'),
    ]

    user     = models.ForeignKey(User, on_delete=models.CASCADE, related_name='system_notifications')
    title    = models.CharField(max_length=200)
    message  = models.TextField()
    emoji    = models.CharField(max_length=10, default='🌍')
    link     = models.CharField(max_length=200, blank=True, default='')
    is_read  = models.BooleanField(default=False)
    read_at  = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    notification_type = models.CharField(max_length=20, choices=TYPE_CHOICES, default=TYPE_SYSTEM)
    # When this notification was generated from an event, link back to it so the
    # event admin can keep the notification in sync on edit / unpublish.
    event = models.ForeignKey(
        'SWASAEvent', null=True, blank=True, on_delete=models.CASCADE,
        related_name='notifications',
    )

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', 'is_read'], name='att_sysnotif_user_unread_idx'),
        ]

    def __str__(self):
        return f"SysNotif → {self.user.username}: {self.title[:50]}"


class SWASAEvent(models.Model):
    EVENT_CHOICES = [
        ('event', 'Event'),
        ('news', 'News'),
        ('announcement', 'Announcement'),
    ]
    title = models.CharField(max_length=200)
    description = models.TextField()
    event_date = models.DateField()
    event_time = models.TimeField(null=True, blank=True)
    venue = models.CharField(max_length=200, blank=True)
    event_type = models.CharField(max_length=20, choices=EVENT_CHOICES, default='event')
    image_url = models.URLField(blank=True)
    is_published = models.BooleanField(default=True)
    # Which student levels this event targets. Empty = everyone (all active
    # users). When set, only students in these levels (plus staff and TAs
    # assigned to them) are notified.
    target_levels = models.ManyToManyField(Level, blank=True, related_name='events')
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='created_events')

    class Meta:
        ordering = ['-event_date']

    def __str__(self):
        return f"{self.get_event_type_display()}: {self.title} ({self.event_date})"


class OTPCode(models.Model):
    PURPOSE_LOGIN = 'login'
    PURPOSE_PASSWORD_RESET = 'password_reset'
    PURPOSE_REGISTRATION = 'registration'
    PURPOSE_CHOICES = [
        (PURPOSE_LOGIN, 'Login'),
        (PURPOSE_PASSWORD_RESET, 'Password Reset'),
        (PURPOSE_REGISTRATION, 'Registration'),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='otp_codes')
    code = models.CharField(max_length=6)
    purpose = models.CharField(max_length=20, choices=PURPOSE_CHOICES)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    is_used = models.BooleanField(default=False)
    magic_token = models.UUIDField(null=True, blank=True, unique=True)
    magic_token_used = models.BooleanField(default=False)
    magic_token_expires_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        indexes = [
            models.Index(fields=['user', 'purpose', 'is_used']),
            models.Index(fields=['magic_token'], name='att_otpcode_magic_token_idx'),
        ]

    def save(self, *args, **kwargs):
        if not self.expires_at:
            self.expires_at = timezone.now() + timedelta(minutes=5)
        super().save(*args, **kwargs)

    def is_expired(self):
        return timezone.now() > self.expires_at

    def __str__(self):
        return f"OTP({self.purpose}) for {self.user.username} — {'used' if self.is_used else 'active'}"