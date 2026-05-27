import csv
import string
import random
from datetime import timedelta

from django.contrib.auth import login
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.models import User
from django.http import JsonResponse, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST
from django.contrib.admin.views.decorators import staff_member_required
from django.db.models import Count, Q
from django.db.models.functions import TruncMonth
from django.core.paginator import Paginator
from django.contrib import messages

from .forms import StudentRegistrationForm
from .models import (
    AttendanceCode, AttendanceRecord, ClassSession,
    Course, UserProfile, Level, Semester,
)


# ── Helpers ──────────────────────────────────────────────────────────────────

def is_lecturer(user):
    return user.is_staff or user.groups.filter(name="Lecturer").exists()


def get_profile(user):
    try:
        return user.userprofile
    except UserProfile.DoesNotExist:
        return None


# ── Student Dashboard ─────────────────────────────────────────────────────────

@login_required
def dashboard(request):
    if is_lecturer(request.user):
        return redirect("attendance:lecturer_dashboard")

    profile = get_profile(request.user)
    if not profile:
        return redirect("login")

    # Only show non-archived semesters
    courses = Course.objects.filter(level=profile.level, semester__is_archived=False).select_related("semester")
    course_data = []

    for course in courses:
        sessions = ClassSession.objects.filter(course=course).order_by("date")
        weeks = []
        for i, session in enumerate(sessions, start=1):
            code_obj = AttendanceCode.objects.filter(
                student=request.user, class_session=session
            ).first()
            record = AttendanceRecord.objects.filter(
                student=request.user, class_session=session
            ).first()

            if record:
                status = "submitted"
            elif code_obj and not code_obj.is_expired():
                status = "generated"
            elif code_obj and code_obj.is_expired():
                status = "expired"
            else:
                status = "not_started"

            weeks.append({
                "week_num": i,
                "session": session,
                "code_obj": code_obj,
                "record": record,
                "status": status,
            })
        course_data.append({"course": course, "weeks": weeks})

    return render(request, "attendance/dashboard.html", {"course_data": course_data})


# ── AJAX: Generate Code ───────────────────────────────────────────────────────

@login_required
@require_POST
def generate_code(request):
    session_id = request.POST.get("session_id")
    session = get_object_or_404(ClassSession, id=session_id)

    if AttendanceRecord.objects.filter(student=request.user, class_session=session).exists():
        return JsonResponse({"error": "Attendance already submitted for this session."}, status=400)

    existing = AttendanceCode.objects.filter(student=request.user, class_session=session).first()
    if existing and not existing.is_expired():
        return JsonResponse({
            "code": existing.code_string,
            "expires_at": existing.expires_at.isoformat(),
            "already_existed": True,
        })

    if existing:
        existing.delete()

    now = timezone.now()
    code_obj = AttendanceCode.objects.create(
        student=request.user,
        class_session=session,
        generated_at=now,
        expires_at=now + timedelta(days=7),
    )

    return JsonResponse({
        "code": code_obj.code_string,
        "expires_at": code_obj.expires_at.isoformat(),
        "already_existed": False,
    })


# ── AJAX: Submit Attendance ───────────────────────────────────────────────────

@login_required
@require_POST
def submit_attendance(request):
    session_id = request.POST.get("session_id")
    session = get_object_or_404(ClassSession, id=session_id)

    if AttendanceRecord.objects.filter(student=request.user, class_session=session).exists():
        return JsonResponse({"error": "Attendance already submitted."}, status=400)

    code_obj = AttendanceCode.objects.filter(
        student=request.user, class_session=session
    ).first()
    if not code_obj:
        return JsonResponse({"error": "No code found. Generate a code first."}, status=400)
    if code_obj.is_expired():
        return JsonResponse({"error": "Your code has expired. Generate a new one."}, status=400)

    AttendanceRecord.objects.create(
        student=request.user,
        class_session=session,
        code=code_obj,
    )
    code_obj.used_at = timezone.now()
    code_obj.save()

    return JsonResponse({"success": True})


# ── Student History ───────────────────────────────────────────────────────────

@login_required
def student_history(request):
    if is_lecturer(request.user):
        return redirect("attendance:lecturer_dashboard")

    profile = get_profile(request.user)
    if not profile:
        return redirect("login")

    courses = Course.objects.filter(level=profile.level, semester__is_archived=False)
    history_data = []
    today = timezone.now().date()

    for course in courses:
        sessions = ClassSession.objects.filter(course=course).order_by("date")
        total = sessions.count()
        attended = 0
        weeks = []

        for i, session in enumerate(sessions, start=1):
            record = AttendanceRecord.objects.filter(
                student=request.user, class_session=session
            ).first()

            if record:
                day_status = "attended"
                attended += 1
            elif session.date < today:
                day_status = "absent"
            else:
                day_status = "future"

            weeks.append({"week_num": i, "session": session, "status": day_status})

        percentage = round((attended / total) * 100) if total else 0
        history_data.append({
            "course": course,
            "weeks": weeks,
            "attended": attended,
            "total": total,
            "percentage": percentage,
        })

    return render(request, "attendance/history.html", {"history_data": history_data})


# ── Lecturer Dashboard ────────────────────────────────────────────────────────

@login_required
@user_passes_test(is_lecturer, login_url="/")
def lecturer_dashboard(request):
    today = timezone.now().date()
    selected_date_str = request.GET.get("date", today.isoformat())
    try:
        from datetime import date
        selected_date = date.fromisoformat(selected_date_str)
    except ValueError:
        selected_date = today

    sessions = ClassSession.objects.filter(date=selected_date).select_related("course", "course__level")
    dashboard_data = []

    for session in sessions:
        course = session.course
        enrolled = UserProfile.objects.filter(level=course.level)
        total_enrolled = enrolled.count()
        generated = AttendanceCode.objects.filter(class_session=session).count()
        submitted = AttendanceRecord.objects.filter(class_session=session).count()

        submitted_user_ids = AttendanceRecord.objects.filter(
            class_session=session
        ).values_list("student_id", flat=True)
        absent_profiles = enrolled.exclude(user_id__in=submitted_user_ids).select_related("user")

        dashboard_data.append({
            "session": session,
            "course": course,
            "total_enrolled": total_enrolled,
            "generated": generated,
            "submitted": submitted,
            "absent_profiles": absent_profiles,
        })

    return render(request, "attendance/lecturer_dashboard.html", {
        "dashboard_data": dashboard_data,
        "selected_date": selected_date,
        "today": today,
    })


# ── CSV Export ────────────────────────────────────────────────────────────────

@login_required
@user_passes_test(is_lecturer, login_url="/")
def export_attendance_csv(request, session_id):
    session = get_object_or_404(ClassSession, id=session_id)
    course = session.course
    enrolled = UserProfile.objects.filter(level=course.level).select_related("user")

    submitted_map = {
        r.student_id: r
        for r in AttendanceRecord.objects.filter(class_session=session).select_related("student")
    }

    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = (
        f'attachment; filename="attendance_{course.code}_{session.date}.csv"'
    )

    writer = csv.writer(response)
    writer.writerow(["Full Name", "Username", "Student ID", "Level", "Status", "Submitted At"])

    for profile in enrolled:
        user = profile.user
        record = submitted_map.get(user.id)
        writer.writerow([
            user.get_full_name() or user.username,
            user.username,
            profile.student_id_number or "-",
            profile.level,
            "Present" if record else "Absent",
            record.submitted_at.strftime("%Y-%m-%d %H:%M") if record else "-",
        ])

    return response


# ── Student Registration ──────────────────────────────────────────────────────

def register(request):
    if request.user.is_authenticated:
        return redirect("attendance:dashboard")
    if request.method == "POST":
        form = StudentRegistrationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            return redirect("attendance:dashboard")
    else:
        form = StudentRegistrationForm()
    return render(request, "attendance/register.html", {"form": form})


# ── Admin Dashboard ───────────────────────────────────────────────────────────

@staff_member_required
def admin_dashboard(request):
    """Admin dashboard with level-wise attendance analytics"""
    
    levels = Level.objects.all()
    level_stats = []
    
    for level in levels:
        students = UserProfile.objects.filter(level=level)
        total_students = students.count()
        
        courses = Course.objects.filter(level=level)
        total_courses = courses.count()
        
        total_sessions = ClassSession.objects.filter(course__in=courses).count()
        
        attendance_records = AttendanceRecord.objects.filter(
            student__userprofile__level=level
        ).count()
        
        expected_attendances = total_students * total_sessions
        attendance_rate = (attendance_records / expected_attendances * 100) if expected_attendances > 0 else 0
        
        level_stats.append({
            'level': level,
            'total_students': total_students,
            'total_courses': total_courses,
            'total_sessions': total_sessions,
            'attendance_records': attendance_records,
            'attendance_rate': round(attendance_rate, 1),
        })
    
    top_students = []
    struggling_students = []
    
    for profile in UserProfile.objects.select_related('user', 'level').all():
        total_sessions = ClassSession.objects.filter(course__level=profile.level).count()
        attended = AttendanceRecord.objects.filter(student=profile.user).count()
        percentage = (attended / total_sessions * 100) if total_sessions > 0 else 0
        
        student_info = {
            'name': profile.user.get_full_name() or profile.user.username,
            'level': profile.level.name,
            'percentage': round(percentage, 1),
        }
        
        if percentage >= 90 and attended > 5:
            top_students.append(student_info)
        elif percentage < 60 and attended > 0:
            struggling_students.append(student_info)
    
    recent_attendance = AttendanceRecord.objects.select_related(
        'student', 'class_session__course'
    ).order_by('-submitted_at')[:10]
    
    context = {
        'level_stats': level_stats,
        'total_students': UserProfile.objects.count(),
        'total_courses': Course.objects.count(),
        'total_sessions': ClassSession.objects.count(),
        'total_attendance_records': AttendanceRecord.objects.count(),
        'top_students': top_students[:5],
        'struggling_students': struggling_students[:5],
        'recent_attendance': recent_attendance,
    }
    
    return render(request, 'attendance/admin_dashboard.html', context)


# ── Student Attendance Report ─────────────────────────────────────────────────

@staff_member_required
def student_attendance_report(request, student_id=None):
    students = UserProfile.objects.select_related('user', 'level').all()
    
    level_id = request.GET.get('level')
    if level_id:
        students = students.filter(level_id=level_id)
    
    search_query = request.GET.get('search')
    if search_query:
        students = students.filter(
            Q(user__first_name__icontains=search_query) |
            Q(user__last_name__icontains=search_query) |
            Q(user__username__icontains=search_query) |
            Q(student_id_number__icontains=search_query)
        )
    
    if student_id:
        students = students.filter(id=student_id)
    
    student_data = []
    for profile in students:
        attendance_records = AttendanceRecord.objects.filter(
            student=profile.user
        ).select_related('class_session__course')
        
        course_attendance = {}
        courses = Course.objects.filter(level=profile.level)
        
        for course in courses:
            total_sessions = ClassSession.objects.filter(course=course).count()
            attended = attendance_records.filter(class_session__course=course).count()
            percentage = (attended / total_sessions * 100) if total_sessions > 0 else 0
            course_attendance[course.code] = {
                'name': course.name,
                'attended': attended,
                'total': total_sessions,
                'percentage': round(percentage, 1)
            }
        
        total_attended = len(attendance_records)
        total_possible = sum(c['total'] for c in course_attendance.values())
        attendance_percentage = (total_attended / total_possible * 100) if total_possible > 0 else 0
        
        alerts = []
        for course_code, data in course_attendance.items():
            if data['percentage'] < 75 and data['total'] > 0:
                alerts.append({
                    'course': data['name'],
                    'percentage': data['percentage'],
                })
        
        student_data.append({
            'profile': profile,
            'attendance_percentage': round(attendance_percentage, 1),
            'course_attendance': course_attendance,
            'alerts': alerts,
        })
    
    context = {
        'students': student_data,
        'levels': Level.objects.all(),
        'selected_level': level_id,
        'search_query': search_query,
    }
    
    return render(request, 'attendance/student_report.html', context)


# ── Export Level Attendance CSV ───────────────────────────────────────────────

@staff_member_required
def export_level_attendance(request, level_id):
    level = get_object_or_404(Level, id=level_id)
    students = UserProfile.objects.filter(level=level).select_related('user')
    courses = Course.objects.filter(level=level)
    
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="attendance_level_{level.name}_{timezone.now().date()}.csv"'
    
    writer = csv.writer(response)
    
    headers = ['Student ID', 'Student Name', 'Level']
    for course in courses:
        headers.append(f'{course.code} Attended')
        headers.append(f'{course.code} Total')
        headers.append(f'{course.code} %')
    headers.append('Overall %')
    writer.writerow(headers)
    
    for profile in students:
        row = [
            profile.student_id_number,
            profile.user.get_full_name() or profile.user.username,
            level.name,
        ]
        
        total_attended = 0
        total_possible = 0
        
        for course in courses:
            total_sessions = ClassSession.objects.filter(course=course).count()
            attended = AttendanceRecord.objects.filter(
                student=profile.user,
                class_session__course=course
            ).count()
            
            percentage = (attended / total_sessions * 100) if total_sessions > 0 else 0
            
            row.append(attended)
            row.append(total_sessions)
            row.append(f"{percentage:.1f}%")
            
            total_attended += attended
            total_possible += total_sessions
        
        overall = (total_attended / total_possible * 100) if total_possible > 0 else 0
        row.append(f"{overall:.1f}%")
        
        writer.writerow(row)
    
    return response


# ── Attendance Trends API ─────────────────────────────────────────────────────

@staff_member_required
def attendance_trends(request):
    trends = []
    levels = Level.objects.all()
    
    for level in levels:
        monthly_data = AttendanceRecord.objects.filter(
            student__userprofile__level=level
        ).annotate(
            month=TruncMonth('submitted_at')
        ).values('month').annotate(
            count=Count('id')
        ).order_by('month')
        
        trends.append({
            'level': level.name,
            'data': list(monthly_data),
        })
    
    return JsonResponse({'trends': trends})


# ── Bulk Student Import ───────────────────────────────────────────────────────

@staff_member_required
def bulk_student_import(request):
    if request.method == 'POST' and request.FILES.get('csv_file'):
        from io import TextIOWrapper
        
        csv_file = request.FILES['csv_file']
        decoded_file = TextIOWrapper(csv_file, encoding='utf-8')
        
        reader = csv.DictReader(decoded_file)
        created_count = 0
        errors = []
        
        for row_num, row in enumerate(reader, start=2):
            try:
                username = row.get('username')
                password = row.get('password', 'swasa2026')
                first_name = row.get('first_name', '')
                last_name = row.get('last_name', '')
                level_name = row.get('level', '100')
                student_id = row.get('student_id', '')
                
                if User.objects.filter(username=username).exists():
                    errors.append(f"Row {row_num}: Username '{username}' already exists")
                    continue
                
                user = User.objects.create_user(
                    username=username,
                    password=password,
                    first_name=first_name,
                    last_name=last_name
                )
                
                level = Level.objects.get(name=level_name)
                
                UserProfile.objects.create(
                    user=user,
                    level=level,
                    student_id_number=student_id
                )
                created_count += 1
                
            except Level.DoesNotExist:
                errors.append(f"Row {row_num}: Level '{level_name}' does not exist")
            except Exception as e:
                errors.append(f"Row {row_num}: {str(e)}")
        
        return JsonResponse({
            'success': True,
            'created': created_count,
            'errors': errors
        })
    
    return render(request, 'attendance/bulk_import.html')


# ── Semester Archiving ─────────────────────────────────────────────────────────

@staff_member_required
def archive_semester(request, semester_id):
    """Archive a semester (hide from students, keep for records)"""
    semester = get_object_or_404(Semester, id=semester_id)
    
    if request.method == 'POST':
        semester.is_archived = True
        semester.is_active = False
        semester.save()
        
        messages.success(request, f'Semester {semester} has been archived.')
        return redirect('attendance:semester_list')
    
    return render(request, 'attendance/archive_semester_confirm.html', {'semester': semester})


@staff_member_required
def activate_semester(request, semester_id):
    """Activate a semester for current use"""
    # Deactivate all semesters first
    Semester.objects.all().update(is_active=False)
    
    # Activate selected semester
    semester = get_object_or_404(Semester, id=semester_id)
    semester.is_active = True
    semester.is_archived = False
    semester.save()
    
    messages.success(request, f'{semester} is now active.')
    return redirect('attendance:semester_list')


@staff_member_required
def semester_list(request):
    """List all semesters with archive/activate options"""
    semesters = Semester.objects.all().order_by('-year', 'name')
    return render(request, 'attendance/semester_list.html', {'semesters': semesters})


# ── Student CSV Export (No PDF) ───────────────────────────────────────────────

@login_required
def export_my_attendance_csv(request):
    """Export current student's attendance as CSV"""
    profile = get_profile(request.user)
    if not profile:
        return redirect('login')
    
    semesters = Semester.objects.filter(is_archived=False)
    courses = Course.objects.filter(level=profile.level, semester__in=semesters)
    
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="attendance_{request.user.username}_{timezone.now().date()}.csv"'
    
    writer = csv.writer(response)
    writer.writerow(['Course Code', 'Course Name', 'Week', 'Date', 'Topic', 'Status', 'Submitted At'])
    
    for course in courses:
        sessions = ClassSession.objects.filter(course=course).order_by('date')
        for i, session in enumerate(sessions, start=1):
            record = AttendanceRecord.objects.filter(student=request.user, class_session=session).first()
            status = "Present" if record else "Absent"
            submitted_at = record.submitted_at.strftime('%Y-%m-%d %H:%M') if record else '-'
            writer.writerow([
                course.code, course.name, i, session.date, session.topic, status, submitted_at
            ])
    
    return response


# ── Admin CSV Export Functions (No PDF) ───────────────────────────────────────

@staff_member_required
def admin_export_student_csv(request, student_id):
    """Admin export specific student's attendance as CSV"""
    student_profile = get_object_or_404(UserProfile, id=student_id)
    student_user = student_profile.user
    
    semesters = Semester.objects.filter(is_archived=False)
    courses = Course.objects.filter(level=student_profile.level, semester__in=semesters)
    
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="attendance_{student_user.username}_{timezone.now().date()}.csv"'
    
    writer = csv.writer(response)
    writer.writerow(['Student ID', 'Student Name', 'Level', 'Course Code', 'Course Name', 'Week', 'Date', 'Topic', 'Status', 'Submitted At'])
    
    for course in courses:
        sessions = ClassSession.objects.filter(course=course).order_by('date')
        for i, session in enumerate(sessions, start=1):
            record = AttendanceRecord.objects.filter(student=student_user, class_session=session).first()
            status = "Present" if record else "Absent"
            submitted_at = record.submitted_at.strftime('%Y-%m-%d %H:%M') if record else '-'
            writer.writerow([
                student_profile.student_id_number or '-',
                student_user.get_full_name() or student_user.username,
                student_profile.level.name,
                course.code, course.name, i, session.date, session.topic, status, submitted_at
            ])
    
    return response


@staff_member_required
def admin_export_all_students_csv(request, level_id=None):
    """Export all students' attendance records as CSV"""
    if level_id:
        students = UserProfile.objects.filter(level_id=level_id).select_related('user', 'level')
        level = get_object_or_404(Level, id=level_id)
        filename = f'all_attendance_level_{level.name}_{timezone.now().date()}.csv'
    else:
        students = UserProfile.objects.all().select_related('user', 'level')
        filename = f'all_attendance_{timezone.now().date()}.csv'
    
    semesters = Semester.objects.filter(is_archived=False)
    
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    
    writer = csv.writer(response)
    writer.writerow(['Student ID', 'Student Name', 'Level', 'Course Code', 'Course Name', 'Week', 'Date', 'Topic', 'Status', 'Submitted At'])
    
    for profile in students:
        courses = Course.objects.filter(level=profile.level, semester__in=semesters)
        for course in courses:
            sessions = ClassSession.objects.filter(course=course).order_by('date')
            for i, session in enumerate(sessions, start=1):
                record = AttendanceRecord.objects.filter(student=profile.user, class_session=session).first()
                status = "Present" if record else "Absent"
                submitted_at = record.submitted_at.strftime('%Y-%m-%d %H:%M') if record else '-'
                writer.writerow([
                    profile.student_id_number or '-',
                    profile.user.get_full_name() or profile.user.username,
                    profile.level.name,
                    course.code, course.name, i, session.date, session.topic, status, submitted_at
                ])
    
    return response


@staff_member_required
def admin_search_students(request):
    """Search students by name, ID, or level"""
    search_query = request.GET.get('q', '')
    level_id = request.GET.get('level')
    
    students = UserProfile.objects.select_related('user', 'level').all()
    
    if search_query:
        students = students.filter(
            Q(user__first_name__icontains=search_query) |
            Q(user__last_name__icontains=search_query) |
            Q(user__username__icontains=search_query) |
            Q(student_id_number__icontains=search_query)
        )
    
    if level_id:
        students = students.filter(level_id=level_id)
    
    student_data = []
    for profile in students:
        semesters = Semester.objects.filter(is_archived=False)
        courses = Course.objects.filter(level=profile.level, semester__in=semesters)
        
        total_sessions = 0
        total_attended = 0
        
        for course in courses:
            sessions = ClassSession.objects.filter(course=course).count()
            attended = AttendanceRecord.objects.filter(student=profile.user, class_session__course=course).count()
            total_sessions += sessions
            total_attended += attended
        
        percentage = (total_attended / total_sessions * 100) if total_sessions > 0 else 0
        
        student_data.append({
            'profile': profile,
            'total_sessions': total_sessions,
            'total_attended': total_attended,
            'percentage': round(percentage, 1),
        })
    
    context = {
        'students': student_data,
        'search_query': search_query,
        'selected_level': level_id,
        'levels': Level.objects.all(),
    }
    
    return render(request, 'attendance/admin_search.html', context)