import random
import string
from datetime import timedelta
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
    is_archived = models.BooleanField(default=False)  # NEW FIELD

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
    topic = models.CharField(max_length=200)
    lecturer = models.ForeignKey(User, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.course} on {self.date}"


class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    level = models.ForeignKey(Level, on_delete=models.SET_NULL, null=True, blank=True)
    student_id_number = models.CharField(max_length=50, blank=True, null=True)

    def __str__(self):
        return f"{self.user.username} - Level {self.level}"


class AttendanceCode(models.Model):
    code_string = models.CharField(max_length=20, unique=True, blank=True)
    student = models.ForeignKey(User, on_delete=models.CASCADE, related_name='codes')
    class_session = models.ForeignKey(ClassSession, on_delete=models.CASCADE)
    generated_at = models.DateTimeField(default=timezone.now)
    expires_at = models.DateTimeField()
    used_at = models.DateTimeField(null=True, blank=True)

    def save(self, *args, **kwargs):
        if not self.code_string:
            self.code_string = ''.join(random.choices(
                string.ascii_uppercase + string.digits, k=8
            ))
        
        if not self.expires_at and self.generated_at:
            self.expires_at = self.generated_at + timedelta(days=7)
        elif not self.expires_at:
            self.expires_at = timezone.now() + timedelta(days=7)
        
        super().save(*args, **kwargs)

    def is_expired(self):
        return timezone.now() > self.expires_at

    def is_used(self):
        return self.used_at is not None

    def __str__(self):
        return f"{self.code_string} for {self.student.username}"


class AttendanceRecord(models.Model):
    student = models.ForeignKey(User, on_delete=models.CASCADE, related_name='attendance')
    class_session = models.ForeignKey(ClassSession, on_delete=models.CASCADE)
    code = models.OneToOneField(AttendanceCode, on_delete=models.CASCADE)
    submitted_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.student.username} attended {self.class_session}"