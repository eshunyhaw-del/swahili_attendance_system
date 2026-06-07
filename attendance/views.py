import csv
import string
import random
import uuid
import jwt
from datetime import timedelta, datetime

from django.conf import settings
from django.contrib.auth import authenticate, login
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.models import User
from django.http import JsonResponse, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST
from django.contrib.admin.views.decorators import staff_member_required
from django.db.models import Count, Q, Max
from django.contrib import messages
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.utils.html import strip_tags

from .forms import StudentRegistrationForm, CourseRegistrationForm, SupportTicketForm, TARegistrationForm
from .models import (
    AttendanceCode, AttendanceRecord, ClassSession,
    Course, UserProfile, Level, Semester, SupportTicket, CodeMisuseAlert,
    TAProfile, TACode, OTPCode, TAnnouncement,
)


# ── Helpers ──────────────────────────────────────────────────────────────────

def is_lecturer(user):
    return (user.is_staff or user.groups.filter(name="Lecturer").exists()) and not hasattr(user, 'taprofile')

def is_student(user):
    return not user.is_staff and not hasattr(user, 'taprofile')

def get_profile(user):
    try:
        return user.userprofile
    except UserProfile.DoesNotExist:
        return None


def send_verification_email(user, token, request):
    """Send email verification link to user"""
    verification_url = f"https://{request.get_host()}/verify-email/{token}/"
    
    html_message = render_to_string('attendance/verification_email.html', {
        'user': user,
        'verification_url': verification_url,
    })
    
    send_mail(
        subject='Verify Your Email - SWASA Attendance',
        message=strip_tags(html_message),
        from_email='noreply@swasa.edu.gh',
        recipient_list=[user.email],
        html_message=html_message,
        fail_silently=False,
    )


def send_ta_approval_email(ta_profile):
    try:
        html_message = render_to_string('attendance/ta_approval_email.html', {
            'ta_profile': ta_profile,
            'login_url': '/login/',
            'dashboard_url': '/ta/dashboard/',
        })
        send_mail(
            subject='Your TA Account Approved - SWASA Attendance',
            message=strip_tags(html_message),
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[ta_profile.user.email],
            html_message=html_message,
            fail_silently=True,
        )
    except Exception:
        pass


def send_ta_rejection_email(ta_profile):
    try:
        html_message = render_to_string('attendance/ta_rejection_email.html', {
            'ta_profile': ta_profile,
        })
        send_mail(
            subject='Your TA Application - SWASA Attendance',
            message=strip_tags(html_message),
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[ta_profile.user.email],
            html_message=html_message,
            fail_silently=True,
        )
    except Exception:
        pass


def generate_and_send_otp(user, purpose, expiry_minutes=5):
    """Generate a 6-digit OTP, invalidate old ones, persist, and email it."""
    OTPCode.objects.filter(user=user, purpose=purpose, is_used=False).update(is_used=True)

    code = f"{random.randint(0, 999999):06d}"
    OTPCode.objects.create(
        user=user,
        code=code,
        purpose=purpose,
        expires_at=timezone.now() + timedelta(minutes=expiry_minutes),
    )

    purpose_labels = {
        OTPCode.PURPOSE_LOGIN: 'login verification',
        OTPCode.PURPOSE_REGISTRATION: 'email verification',
        OTPCode.PURPOSE_PASSWORD_RESET: 'password reset',
    }
    label = purpose_labels.get(purpose, 'verification')

    send_mail(
        subject='Your SWASA Verification Code',
        message=(
            f"Hello {user.get_full_name() or user.username},\n\n"
            f"Your SWASA {label} code is:\n\n"
            f"    {code}\n\n"
            f"This code expires in {expiry_minutes} minutes.\n\n"
            f"If you did not request this, please ignore this email.\n\n"
            f"— SWASA Attendance System"
        ),
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[user.email],
        fail_silently=False,
    )


# ── Token-based Login / Logout ───────────────────────────────────────────────

def token_login_view(request):
    if request.user.is_authenticated:
        if request.user.is_staff:
            return redirect(reverse('attendance:admin_dashboard'))
        if hasattr(request.user, 'taprofile'):
            return redirect(reverse('attendance:ta_dashboard'))
        return redirect(reverse('attendance:dashboard'))

    if request.method == 'POST':
        email = request.POST.get('email', '').strip().lower()
        password = request.POST.get('password', '').strip()
        remember_me = request.POST.get('remember_me')

        # Look up user by email, then authenticate with their username
        user = None
        try:
            email_user = User.objects.get(email__iexact=email, is_active=True)
            user = authenticate(request, username=email_user.username, password=password)
        except User.DoesNotExist:
            pass

        if user is not None and user.is_active:
            next_url = request.POST.get('next', '').strip()
            if not next_url or not url_has_allowed_host_and_scheme(next_url, allowed_hosts={request.get_host()}):
                if user.is_staff:
                    next_url = reverse('attendance:admin_dashboard')
                elif hasattr(user, 'taprofile'):
                    next_url = reverse('attendance:ta_dashboard')
                else:
                    next_url = reverse('attendance:dashboard')

            access_expiry = timedelta(days=30 if remember_me else 1)
            refresh_expiry = timedelta(days=60 if remember_me else 7)
            now = datetime.utcnow()

            access_token = jwt.encode(
                {'user_id': user.id, 'username': user.username,
                 'exp': now + access_expiry, 'iat': now},
                settings.JWT_SECRET_KEY, algorithm='HS256'
            )
            refresh_token = jwt.encode(
                {'user_id': user.id, 'type': 'refresh',
                 'exp': now + refresh_expiry, 'iat': now},
                settings.JWT_SECRET_KEY, algorithm='HS256'
            )

            response = redirect(next_url)
            is_secure = not settings.DEBUG
            response.set_cookie('access_token', access_token,
                                max_age=int(access_expiry.total_seconds()),
                                httponly=True, secure=is_secure, samesite='Lax')
            response.set_cookie('refresh_token', refresh_token,
                                max_age=int(refresh_expiry.total_seconds()),
                                httponly=True, secure=is_secure, samesite='Lax')
            return response

        return render(request, 'attendance/login.html', {
            'login_error': True,
            'next': request.POST.get('next', ''),
        })

    return render(request, 'attendance/login.html', {
        'next': request.GET.get('next', ''),
    })


def token_logout_view(request):
    response = redirect('login')
    response.delete_cookie('access_token')
    response.delete_cookie('refresh_token')
    return response


# ── Student Registration ──────────────────────────────────────────────────────

def register(request):
    if request.user.is_authenticated:
        return redirect("attendance:dashboard")

    if request.method == "POST":
        form = StudentRegistrationForm(request.POST)
        if form.is_valid():
            user = form.save()
            try:
                generate_and_send_otp(user, OTPCode.PURPOSE_REGISTRATION, expiry_minutes=10)
            except Exception:
                user.delete()
                messages.error(request, "Could not send verification email. Please try again.")
                return render(request, "attendance/register.html", {"form": form})
            request.session['pending_reg_user_id'] = user.id
            request.session['pending_reg_type'] = 'student'
            return redirect("attendance:otp_verify_registration")
        else:
            messages.error(request, "Please correct the errors below.")
    else:
        form = StudentRegistrationForm()

    return render(request, "attendance/register.html", {"form": form})


def verify_email(request, token):
    """Verify user's email address (kept for backward compatibility)"""
    try:
        profile = UserProfile.objects.get(email_verification_token=token, email_verified=False)
        user = profile.user
        user.is_active = True
        user.save()
        profile.email_verified = True
        profile.email_verification_token = None
        profile.verification_sent_at = timezone.now()
        profile.save()

        messages.success(request, "Email verified! You can now login.")
        return redirect('login')
    except UserProfile.DoesNotExist:
        messages.error(request, "Invalid or expired verification link.")
        return redirect('register')


# ── OTP: Registration Verification ───────────────────────────────────────────

def otp_verify_registration(request):
    user_id = request.session.get('pending_reg_user_id')
    reg_type = request.session.get('pending_reg_type', 'student')

    if not user_id:
        return redirect('attendance:register')

    try:
        user = User.objects.get(id=user_id, is_active=False)
    except User.DoesNotExist:
        return redirect('attendance:register')

    error = None

    if request.method == 'POST':
        action = request.POST.get('action')

        if action == 'resend':
            try:
                generate_and_send_otp(user, OTPCode.PURPOSE_REGISTRATION, expiry_minutes=10)
                messages.success(request, "A new verification code was sent.")
            except Exception:
                messages.error(request, "Could not resend. Please try again.")
            return redirect('attendance:otp_verify_registration')

        entered = request.POST.get('otp_code', '').strip()
        otp = OTPCode.objects.filter(
            user=user, code=entered,
            purpose=OTPCode.PURPOSE_REGISTRATION, is_used=False,
        ).first()

        if not otp or otp.is_expired():
            error = 'Invalid or expired code. Please try again or request a new code.'
        else:
            otp.is_used = True
            otp.save()
            user.is_active = True
            user.save()

            if reg_type == 'ta':
                try:
                    ta_prof = user.taprofile
                    ta_prof.is_approved = True
                    ta_prof.save()
                except Exception:
                    pass
                redirect_url = reverse('attendance:ta_dashboard')
            else:
                profile = getattr(user, 'userprofile', None)
                if profile:
                    profile.email_verified = True
                    profile.save()
                redirect_url = reverse('attendance:course_registration')

            request.session.pop('pending_reg_user_id', None)
            request.session.pop('pending_reg_type', None)

            # Issue JWT so user is immediately logged in after redirect
            access_expiry = timedelta(days=1)
            refresh_expiry = timedelta(days=7)
            now = datetime.utcnow()
            access_token = jwt.encode(
                {'user_id': user.id, 'username': user.username,
                 'exp': now + access_expiry, 'iat': now},
                settings.JWT_SECRET_KEY, algorithm='HS256'
            )
            refresh_token = jwt.encode(
                {'user_id': user.id, 'type': 'refresh',
                 'exp': now + refresh_expiry, 'iat': now},
                settings.JWT_SECRET_KEY, algorithm='HS256'
            )

            context = {
                'email': user.email,
                'purpose': 'registration',
                'reg_type': reg_type,
                'expiry_minutes': 10,
                'success': True,
                'redirect_url': redirect_url,
            }
            resp = render(request, 'attendance/otp_verify.html', context)
            is_secure = not settings.DEBUG
            resp.set_cookie('access_token', access_token,
                            max_age=int(access_expiry.total_seconds()),
                            httponly=True, secure=is_secure, samesite='Lax')
            resp.set_cookie('refresh_token', refresh_token,
                            max_age=int(refresh_expiry.total_seconds()),
                            httponly=True, secure=is_secure, samesite='Lax')
            return resp

    return render(request, 'attendance/otp_verify.html', {
        'email': user.email,
        'purpose': 'registration',
        'reg_type': reg_type,
        'expiry_minutes': 10,
        'error': error,
    })


# ── OTP: Login 2FA Verification ───────────────────────────────────────────────

def otp_verify_login(request):
    user_id = request.session.get('login_pending_user_id')

    if not user_id:
        return redirect('login')

    try:
        user = User.objects.get(id=user_id)
    except User.DoesNotExist:
        return redirect('login')

    error = None

    if request.method == 'POST':
        action = request.POST.get('action')

        if action == 'resend':
            try:
                generate_and_send_otp(user, OTPCode.PURPOSE_LOGIN, expiry_minutes=5)
                messages.success(request, "A new code was sent.")
            except Exception:
                messages.error(request, "Could not resend. Please try again.")
            return redirect('attendance:otp_verify_login')

        entered = request.POST.get('otp_code', '').strip()
        otp = OTPCode.objects.filter(
            user=user, code=entered,
            purpose=OTPCode.PURPOSE_LOGIN, is_used=False,
        ).first()

        if not otp or otp.is_expired():
            error = 'Invalid or expired code. Please try again or request a new code.'
        else:
            otp.is_used = True
            otp.save()

            next_url = request.session.pop('login_next_url', reverse('attendance:dashboard'))
            remember_me = request.session.pop('login_remember_me', False)
            request.session.pop('login_pending_user_id', None)

            access_expiry = timedelta(days=30 if remember_me else 1)
            refresh_expiry = timedelta(days=60 if remember_me else 7)
            now = datetime.utcnow()

            access_token = jwt.encode(
                {'user_id': user.id, 'username': user.username,
                 'exp': now + access_expiry, 'iat': now},
                settings.JWT_SECRET_KEY, algorithm='HS256'
            )
            refresh_token = jwt.encode(
                {'user_id': user.id, 'type': 'refresh',
                 'exp': now + refresh_expiry, 'iat': now},
                settings.JWT_SECRET_KEY, algorithm='HS256'
            )

            response = redirect(next_url)
            is_secure = not settings.DEBUG
            response.set_cookie('access_token', access_token,
                                max_age=int(access_expiry.total_seconds()),
                                httponly=True, secure=is_secure, samesite='Lax')
            response.set_cookie('refresh_token', refresh_token,
                                max_age=int(refresh_expiry.total_seconds()),
                                httponly=True, secure=is_secure, samesite='Lax')
            return response

    return render(request, 'attendance/otp_verify.html', {
        'email': user.email,
        'purpose': 'login',
        'expiry_minutes': 5,
        'error': error,
    })


# ── OTP: Password Reset ───────────────────────────────────────────────────────

def otp_password_reset_request(request):
    if request.method == 'POST':
        email = request.POST.get('email', '').strip().lower()
        try:
            user = User.objects.get(email__iexact=email, is_active=True)
            generate_and_send_otp(user, OTPCode.PURPOSE_PASSWORD_RESET, expiry_minutes=5)
            request.session['reset_pending_user_id'] = user.id
        except User.DoesNotExist:
            pass
        # Always redirect — don't reveal whether the email exists
        return redirect(reverse('attendance:otp_verify_password_reset'))

    return render(request, 'attendance/otp_password_reset_request.html')


def otp_verify_password_reset(request):
    user_id = request.session.get('reset_pending_user_id')

    if not user_id:
        return redirect('attendance:otp_password_reset')

    try:
        user = User.objects.get(id=user_id)
    except User.DoesNotExist:
        return redirect('attendance:otp_password_reset')

    error = None

    if request.method == 'POST':
        action = request.POST.get('action')

        if action == 'resend':
            try:
                generate_and_send_otp(user, OTPCode.PURPOSE_PASSWORD_RESET, expiry_minutes=5)
                messages.success(request, "A new code was sent.")
            except Exception:
                messages.error(request, "Could not resend. Please try again.")
            return redirect('attendance:otp_verify_password_reset')

        entered = request.POST.get('otp_code', '').strip()
        otp = OTPCode.objects.filter(
            user=user, code=entered,
            purpose=OTPCode.PURPOSE_PASSWORD_RESET, is_used=False,
        ).first()

        if not otp or otp.is_expired():
            error = 'Invalid or expired code. Please try again or request a new code.'
        else:
            otp.is_used = True
            otp.save()
            request.session.pop('reset_pending_user_id', None)
            request.session['reset_verified_user_id'] = user.id
            return render(request, 'attendance/otp_verify.html', {
                'email': user.email,
                'purpose': 'password_reset',
                'expiry_minutes': 5,
                'success': True,
                'redirect_url': reverse('attendance:otp_set_password'),
            })

    return render(request, 'attendance/otp_verify.html', {
        'email': user.email,
        'purpose': 'password_reset',
        'expiry_minutes': 5,
        'error': error,
    })


def otp_set_password(request):
    user_id = request.session.get('reset_verified_user_id')

    if not user_id:
        return redirect('attendance:otp_password_reset')

    try:
        user = User.objects.get(id=user_id)
    except User.DoesNotExist:
        return redirect('attendance:otp_password_reset')

    error = None

    if request.method == 'POST':
        new_password = request.POST.get('new_password', '')
        confirm_password = request.POST.get('confirm_password', '')

        if len(new_password) < 8:
            error = 'Password must be at least 8 characters.'
        elif new_password != confirm_password:
            error = 'Passwords do not match.'
        else:
            user.set_password(new_password)
            user.save()
            request.session.pop('reset_verified_user_id', None)
            messages.success(request, "Password reset successfully! You can now log in.")
            return redirect('login')

    return render(request, 'attendance/otp_set_password.html', {'error': error})


# ── Course Registration ──────────────────────────────────────────────────────

@login_required
def course_registration(request):
    profile = get_profile(request.user)
    if not profile:
        return redirect('login')
    
    active_semester = Semester.objects.filter(is_archived=False, is_active=True).first()
    if not active_semester:
        active_semester = Semester.objects.filter(is_archived=False).first()
    
    if request.method == 'POST':
        form = CourseRegistrationForm(request.POST, level=profile.level, semester=active_semester)
        if form.is_valid():
            selected_courses = form.cleaned_data['courses']
            current_ids = set(profile.registered_courses.values_list('id', flat=True))

            already_registered = []
            newly_added = []
            for course in selected_courses:
                if course.id in current_ids:
                    already_registered.append(str(course))
                else:
                    profile.registered_courses.add(course)
                    newly_added.append(str(course))

            if newly_added:
                messages.success(request, f"Registered for {len(newly_added)} new course(s): {', '.join(newly_added)}")
            if already_registered:
                messages.warning(request, f"Already registered: {', '.join(already_registered)}")
            if not newly_added and not already_registered:
                messages.info(request, "No courses were selected.")

            return redirect('attendance:dashboard')
    else:
        already_registered_ids = list(profile.registered_courses.values_list('id', flat=True))
        form = CourseRegistrationForm(
            level=profile.level, semester=active_semester,
            initial={'courses': already_registered_ids}
        )
    
    context = {
        'form': form,
        'level': profile.level,
        'semester': active_semester,
    }
    return render(request, 'attendance/course_registration.html', context)


# ── Student Dashboard ─────────────────────────────────────────────────────────

@login_required
def dashboard(request):
    # Check if user is TA first
    if hasattr(request.user, 'taprofile'):
        return redirect("attendance:ta_dashboard")
    
    if is_lecturer(request.user):
        return redirect("attendance:lecturer_dashboard")

    profile = get_profile(request.user)
    if not profile:
        return redirect("login")

    if not profile.registered_courses.exists():
        return redirect("attendance:course_registration")

    courses = profile.registered_courses.filter(semester__is_archived=False).select_related("semester")
    course_data = []
    today = timezone.now().date()

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

            is_future = session.date > today
            
            if record:
                status = "submitted"
                status_text = "✓ Submitted"
                status_class = "submitted"
                can_submit = False
            else:
                status = "not_started"
                status_text = "Submit Code"
                status_class = "pending"
                can_submit = True

            weeks.append({
                "week_num": i,
                "session": session,
                "code_obj": code_obj,
                "record": record,
                "status": status,
                "status_text": status_text,
                "status_class": status_class,
                "can_submit": can_submit,
                "is_future": is_future,
            })
        
        total_sessions = len(sessions)
        attended = sum(1 for w in weeks if w['record'])
        percentage = round((attended / total_sessions) * 100) if total_sessions > 0 else 0
        
        course_data.append({
            "course": course,
            "weeks": weeks,
            "total_sessions": total_sessions,
            "attended": attended,
            "percentage": percentage,
        })

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
    if existing:
        existing.delete()

    code_obj = AttendanceCode.objects.create(
        student=request.user,
        class_session=session,
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
    entered_code = request.POST.get("code", "").strip().upper()
    
    session = get_object_or_404(ClassSession, id=session_id)

    if AttendanceRecord.objects.filter(student=request.user, class_session=session).exists():
        return JsonResponse({"error": "Attendance already submitted."}, status=400)

    try:
        code_obj = AttendanceCode.objects.get(code_string=entered_code)
    except AttendanceCode.DoesNotExist:
        return JsonResponse({"error": "Invalid code. Please generate your own code first."}, status=400)

    if code_obj.class_session != session:
        CodeMisuseAlert.objects.create(
            code=code_obj,
            attempted_by=request.user,
            reason=f"Student {request.user.username} submitted code for session {code_obj.class_session_id} against session {session.id}"
        )
        return JsonResponse({"error": "This code is not valid for this session."}, status=400)

    if code_obj.student != request.user:
        CodeMisuseAlert.objects.create(
            code=code_obj,
            attempted_by=request.user,
            reason=f"Student {request.user.username} tried to use code belonging to {code_obj.student.username}"
        )
        return JsonResponse({"error": "This code belongs to another student. You must generate your own code."}, status=400)

    can_use, message = code_obj.can_use()
    if not can_use:
        return JsonResponse({"error": message}, status=400)

    ip_address = request.META.get("HTTP_X_FORWARDED_FOR", request.META.get("REMOTE_ADDR", "")).split(",")[0].strip()
    AttendanceRecord.objects.create(
        student=request.user,
        class_session=session,
        code=code_obj,
        ip_address=ip_address or None,
        user_agent=request.META.get("HTTP_USER_AGENT", ""),
    )
    code_obj.used_at = timezone.now()
    code_obj.save()

    return JsonResponse({"success": True})


# ── Support Ticket ───────────────────────────────────────────────────────────

@login_required
def support(request):
    if request.method == 'POST':
        form = SupportTicketForm(request.POST)
        if form.is_valid():
            ticket = form.save(commit=False)
            ticket.student = request.user
            ticket.save()
            messages.success(request, "Support ticket submitted successfully! Admin will respond soon.")
            return redirect('attendance:support')
    else:
        form = SupportTicketForm()
    
    tickets = SupportTicket.objects.filter(student=request.user).order_by('-created_at')
    
    context = {
        'form': form,
        'tickets': tickets,
    }
    return render(request, 'attendance/support.html', context)


# ── Student History ───────────────────────────────────────────────────────────

@login_required
def student_history(request):
    if hasattr(request.user, 'taprofile'):
        return redirect("attendance:ta_history")
    if is_lecturer(request.user):
        return redirect("attendance:lecturer_dashboard")

    profile = get_profile(request.user)
    if not profile:
        return redirect("login")

    courses = profile.registered_courses.filter(semester__is_archived=False)
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


# ── Student CSV Export ───────────────────────────────────────────────────────

@login_required
def export_my_attendance_csv(request):
    profile = get_profile(request.user)
    if not profile:
        return redirect('login')
    
    semesters = Semester.objects.filter(is_archived=False)
    courses = profile.registered_courses.filter(semester__in=semesters)
    
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


# ── Lecturer Dashboard ────────────────────────────────────────────────────────

@login_required
@user_passes_test(is_lecturer, login_url="/")
def lecturer_dashboard(request):
    today = timezone.now().date()
    selected_date_str = request.GET.get("date", today.isoformat())
    try:
        selected_date = datetime.strptime(selected_date_str, "%Y-%m-%d").date()
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


# ── CSV Export for Lecturer ───────────────────────────────────────────────────

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
            profile.level.name,
            "Present" if record else "Absent",
            record.submitted_at.strftime("%Y-%m-%d %H:%M") if record else "-",
        ])

    return response


# ── Admin Dashboard ───────────────────────────────────────────────────────────

@staff_member_required
def admin_dashboard(request):
    # ── Per-level stats ───────────────────────────────────────────────────────
    level_stats = []
    for level in Level.objects.all():
        lvl_students = UserProfile.objects.filter(level=level).count()
        lvl_courses   = Course.objects.filter(level=level)
        lvl_course_ids = list(lvl_courses.values_list('id', flat=True))
        lvl_sessions  = ClassSession.objects.filter(course_id__in=lvl_course_ids).count()
        lvl_records   = AttendanceRecord.objects.filter(
            student__userprofile__level=level
        ).count()
        expected = lvl_students * lvl_sessions
        lvl_rate = round((lvl_records / expected * 100) if expected > 0 else 0, 1)
        level_stats.append({
            'level': level,
            'total_students': lvl_students,
            'total_courses': lvl_courses.count(),
            'total_sessions': lvl_sessions,
            'attendance_records': lvl_records,
            'attendance_rate': lvl_rate,
        })

    # ── Global totals ─────────────────────────────────────────────────────────
    total_students          = UserProfile.objects.count()
    total_courses           = Course.objects.count()
    total_sessions          = ClassSession.objects.count()
    total_attendance_records = AttendanceRecord.objects.count()
    total_possible          = total_students * total_sessions
    overall_attendance_rate = round(
        (total_attendance_records / total_possible * 100) if total_possible > 0 else 0, 1
    )

    # ── Notification counts ───────────────────────────────────────────────────
    misuse_alerts_count = CodeMisuseAlert.objects.filter(is_resolved=False).count()
    pending_tickets     = SupportTicket.objects.filter(status='pending').count()
    active_tas_count    = TAProfile.objects.filter(is_approved=True).count()

    # ── TA activity stats (bulk — no N+1) ────────────────────────────────────
    ta_activity_map = {
        row['ta_id']: row
        for row in TACode.objects
            .values('ta_id')
            .annotate(
                codes_generated=Count('id'),
                sessions_active=Count('class_session', distinct=True),
                last_active=Max('generated_at'),
            )
    }
    ta_stats = []
    for ta_profile in TAProfile.objects.filter(is_approved=True).select_related('user').prefetch_related('assigned_levels'):
        act = ta_activity_map.get(ta_profile.user_id, {})
        ta_stats.append({
            'profile': ta_profile,
            'codes_generated': act.get('codes_generated', 0),
            'sessions_active': act.get('sessions_active', 0),
            'last_active': act.get('last_active'),
        })
    ta_stats.sort(key=lambda x: x['codes_generated'], reverse=True)

    # ── At-risk students (<75% attendance, bulk queries) ──────────────────────
    all_profiles = list(
        UserProfile.objects.select_related('level', 'user').prefetch_related('registered_courses')
    )
    all_course_ids = {c.id for p in all_profiles for c in p.registered_courses.all()}
    sessions_by_course = {
        row['course_id']: row['count']
        for row in ClassSession.objects
            .filter(course_id__in=all_course_ids)
            .values('course_id')
            .annotate(count=Count('id'))
    } if all_course_ids else {}

    attended_by_student = {
        row['student_id']: row['attended']
        for row in AttendanceRecord.objects
            .filter(student_id__in=[p.user_id for p in all_profiles])
            .values('student_id')
            .annotate(attended=Count('id'))
    }

    at_risk_list = []
    for profile in all_profiles:
        possible = sum(sessions_by_course.get(c.id, 0) for c in profile.registered_courses.all())
        attended = attended_by_student.get(profile.user_id, 0)
        if possible > 0:
            pct = (attended / possible) * 100
            if pct < 75:
                at_risk_list.append({
                    'profile': profile,
                    'percentage': round(pct, 1),
                    'attended': attended,
                    'expected': possible,
                })
    at_risk_list.sort(key=lambda x: x['percentage'])

    # Annotate per-level at-risk counts
    level_id_to_at_risk = {}
    for item in at_risk_list:
        lid = item['profile'].level_id
        level_id_to_at_risk[lid] = level_id_to_at_risk.get(lid, 0) + 1
    for stat in level_stats:
        stat['at_risk'] = level_id_to_at_risk.get(stat['level'].id, 0)

    context = {
        'level_stats': level_stats,
        'total_students': total_students,
        'total_courses': total_courses,
        'total_sessions': total_sessions,
        'total_attendance_records': total_attendance_records,
        'overall_attendance_rate': overall_attendance_rate,
        'misuse_alerts_count': misuse_alerts_count,
        'pending_tickets': pending_tickets,
        'active_tas_count': active_tas_count,
        'ta_stats': ta_stats,
        'at_risk_count': len(at_risk_list),
        'at_risk_preview': at_risk_list[:12],
    }
    return render(request, 'attendance/admin_dashboard.html', context)


# ── Admin Pending TAs ─────────────────────────────────────────────────────────

@staff_member_required
def pending_tas(request):
    pending_ta_list = (
        TAProfile.objects
        .filter(is_approved=False)
        .select_related('user')
        .prefetch_related('assigned_levels')
    )

    if request.method == 'POST':
        ta_profile_id = request.POST.get('ta_profile_id')
        action = request.POST.get('action')
        ta_profile = get_object_or_404(TAProfile, id=ta_profile_id)

        if action == 'approve':
            try:
                ta_profile.is_approved = True
                ta_profile.approved_by = request.user
                ta_profile.approved_at = timezone.now()
                ta_profile.approval_notes = request.POST.get('approval_notes', '')
                ta_profile.save()
                send_ta_approval_email(ta_profile)
                messages.success(request, f"TA {ta_profile.user.get_full_name() or ta_profile.user.username} approved successfully.")
            except Exception:
                messages.error(request, "Approval failed — please try again.")
        elif action == 'reject':
            try:
                username = ta_profile.user.get_full_name() or ta_profile.user.username
                send_ta_rejection_email(ta_profile)
                ta_profile.user.delete()
                messages.success(request, f"Application from {username} rejected and removed.")
            except Exception:
                messages.error(request, "Rejection failed — please try again.")

        return redirect(reverse('attendance:pending_tas'))

    paginator = Paginator(pending_ta_list, 20)
    page_obj = paginator.get_page(request.GET.get('page'))

    return render(request, 'attendance/pending_tas.html', {'pending_tas': page_obj})


# ── Admin Export Level ────────────────────────────────────────────────────────

@staff_member_required
def export_level_attendance(request, level_id):
    level = get_object_or_404(Level, id=level_id)
    students = UserProfile.objects.filter(level=level).select_related('user')
    courses = Course.objects.filter(level=level)
    
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="attendance_level_{level.name}_{timezone.now().date()}.csv"'
    
    # Bulk fetch: sessions per course for this level
    session_counts = (
        ClassSession.objects.filter(course__in=courses)
        .values('course_id')
        .annotate(count=Count('id'))
    )
    sessions_by_course = {row['course_id']: row['count'] for row in session_counts}

    # Bulk fetch: attendance per (student, course) for this level
    student_ids = [p.user_id for p in students]
    attended_counts = (
        AttendanceRecord.objects.filter(
            student_id__in=student_ids,
            class_session__course__in=courses,
        )
        .values('student_id', 'class_session__course_id')
        .annotate(count=Count('id'))
    )
    attended_map = {}
    for row in attended_counts:
        attended_map[(row['student_id'], row['class_session__course_id'])] = row['count']

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
            profile.student_id_number or '-',
            profile.user.get_full_name() or profile.user.username,
            level.name,
        ]

        total_attended = 0
        total_possible = 0

        for course in courses:
            total_sessions = sessions_by_course.get(course.id, 0)
            attended = attended_map.get((profile.user_id, course.id), 0)
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


# ── Admin Student Report ──────────────────────────────────────────────────────

@staff_member_required
def student_attendance_report(request):
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

    students = list(students.prefetch_related('registered_courses'))
    student_ids = [p.user_id for p in students]
    level_ids = list({p.level_id for p in students if p.level_id})

    # Bulk: sessions per course for relevant levels
    session_counts = (
        ClassSession.objects.filter(course__level_id__in=level_ids)
        .values('course_id')
        .annotate(count=Count('id'))
    )
    sessions_by_course = {row['course_id']: row['count'] for row in session_counts}

    # Bulk: courses per level
    all_courses = Course.objects.filter(level_id__in=level_ids).select_related('level')
    courses_by_level = {}
    for course in all_courses:
        courses_by_level.setdefault(course.level_id, []).append(course)

    # Bulk: attendance per (student, course)
    attended_counts = (
        AttendanceRecord.objects.filter(student_id__in=student_ids)
        .values('student_id', 'class_session__course_id')
        .annotate(count=Count('id'))
    )
    attended_map = {}
    for row in attended_counts:
        attended_map[(row['student_id'], row['class_session__course_id'])] = row['count']

    student_data = []
    for profile in students:
        courses = courses_by_level.get(profile.level_id, [])
        course_attendance = {}

        for course in courses:
            total_sessions = sessions_by_course.get(course.id, 0)
            attended = attended_map.get((profile.user_id, course.id), 0)
            percentage = (attended / total_sessions * 100) if total_sessions > 0 else 0
            course_attendance[course.code] = {
                'name': course.name,
                'attended': attended,
                'total': total_sessions,
                'percentage': round(percentage, 1),
            }

        total_attended = sum(c['attended'] for c in course_attendance.values())
        total_possible = sum(c['total'] for c in course_attendance.values())
        attendance_percentage = (total_attended / total_possible * 100) if total_possible > 0 else 0

        alerts = [
            {'course': data['name'], 'percentage': data['percentage']}
            for data in course_attendance.values()
            if data['percentage'] < 75 and data['total'] > 0
        ]

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


# ── Admin Support Tickets ─────────────────────────────────────────────────────

@staff_member_required
def admin_support_tickets(request):
    tickets = SupportTicket.objects.all().order_by('-created_at').select_related('student')

    if request.method == 'POST':
        ticket_id = request.POST.get('ticket_id')
        response_text = request.POST.get('response')
        status = request.POST.get('status')
        ticket = get_object_or_404(SupportTicket, id=ticket_id)
        ticket.admin_response = response_text
        ticket.status = status
        ticket.save()
        messages.success(request, f"Response sent to {ticket.student.username}")
        return redirect('attendance:admin_support')

    paginator = Paginator(tickets, 20)
    page_obj = paginator.get_page(request.GET.get('page'))

    context = {'tickets': page_obj}
    return render(request, 'attendance/admin_support.html', context)


# ── Admin Alerts ──────────────────────────────────────────────────────────────

@staff_member_required
def admin_alerts(request):
    alerts = CodeMisuseAlert.objects.all().order_by('-attempted_at')
    
    if request.method == 'POST':
        alert_id = request.POST.get('alert_id')
        alert = get_object_or_404(CodeMisuseAlert, id=alert_id)
        alert.is_resolved = True
        alert.save()
        messages.success(request, "Alert marked as resolved")
        return redirect('attendance:admin_alerts')
    
    context = {'alerts': alerts}
    return render(request, 'attendance/admin_alerts.html', context)


# ── Admin Export Student CSV ──────────────────────────────────────────────────

@staff_member_required
def admin_export_student_csv(request, student_id):
    student_profile = get_object_or_404(UserProfile, id=student_id)
    student_user = student_profile.user
    
    semesters = Semester.objects.filter(is_archived=False)
    courses = student_profile.registered_courses.filter(semester__in=semesters)
    
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


# ── Admin Export All Students CSV ─────────────────────────────────────────────

@staff_member_required
def admin_export_all_students_csv(request, level_id=None):
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
        courses = profile.registered_courses.filter(semester__in=semesters)
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


# ── Admin Search Students ─────────────────────────────────────────────────────

@staff_member_required
def admin_search_students(request):
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
    
    active_semesters = Semester.objects.filter(is_archived=False)

    # Bulk: sessions per course
    session_counts = (
        ClassSession.objects.filter(course__semester__in=active_semesters)
        .values('course_id')
        .annotate(count=Count('id'))
    )
    sessions_by_course = {row['course_id']: row['count'] for row in session_counts}

    # Bulk: attendance records per (student, course)
    student_ids = [p.user_id for p in students]
    attended_counts = (
        AttendanceRecord.objects.filter(student_id__in=student_ids)
        .values('student_id', 'class_session__course_id')
        .annotate(count=Count('id'))
    )
    attended_map = {}
    for row in attended_counts:
        attended_map[(row['student_id'], row['class_session__course_id'])] = row['count']

    students = students.prefetch_related('registered_courses')

    student_data = []
    for profile in students:
        courses = profile.registered_courses.filter(semester__in=active_semesters)
        total_sessions = sum(sessions_by_course.get(c.id, 0) for c in courses)
        total_attended = sum(attended_map.get((profile.user_id, c.id), 0) for c in courses)
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


# ── TA Registration and Dashboard ─────────────────────────────────────────────

def ta_register(request):
    if request.user.is_authenticated:
        return redirect("attendance:dashboard")

    if request.method == "POST":
        form = TARegistrationForm(request.POST)
        if form.is_valid():
            user = form.save()
            try:
                generate_and_send_otp(user, OTPCode.PURPOSE_REGISTRATION, expiry_minutes=10)
            except Exception:
                user.delete()
                messages.error(request, "Could not send verification email. Please try again.")
                return render(request, "attendance/ta_register.html", {"form": form})
            request.session['pending_reg_user_id'] = user.id
            request.session['pending_reg_type'] = 'ta'
            return redirect("attendance:otp_verify_registration")
        else:
            messages.error(request, "Please correct the errors below.")
    else:
        form = TARegistrationForm()

    return render(request, "attendance/ta_register.html", {"form": form})


@login_required
def ta_history(request):
    """TA history — per-session code generation record."""
    if not hasattr(request.user, 'taprofile'):
        return redirect('attendance:dashboard')

    ta_profile = request.user.taprofile
    if not ta_profile.is_approved:
        return redirect('attendance:ta_dashboard')

    assigned_level_ids = list(ta_profile.assigned_levels.values_list('id', flat=True))

    sessions = ClassSession.objects.filter(
        course__level__id__in=assigned_level_ids,
        course__semester__is_active=True,
    ).select_related('course', 'course__level').order_by('course__code', 'date')

    # Fetch all TACode stats for this TA across all sessions in one query
    from django.db.models import Count, Q as DQ
    stats_qs = (
        TACode.objects
        .filter(ta=request.user, class_session__in=sessions)
        .values('class_session_id')
        .annotate(
            generated=Count('id'),
            used=Count('id', filter=DQ(is_used=True)),
            given=Count('id', filter=DQ(is_distributed=True)),
        )
    )
    stats_by_session = {s['class_session_id']: s for s in stats_qs}

    # Student counts per course (one query)
    from django.db.models import Count as _Count
    course_ids = list({s.course_id for s in sessions})
    student_counts = {
        row['registered_courses']: row['cnt']
        for row in UserProfile.objects.filter(registered_courses__in=course_ids)
        .values('registered_courses')
        .annotate(cnt=_Count('id'))
    }

    # Group sessions by course, building history entries
    courses_history = {}
    total_generated = 0
    total_used = 0

    for session in sessions:
        cid = session.course_id
        if cid not in courses_history:
            courses_history[cid] = {'course': session.course, 'sessions': [], '_week': 0}
        courses_history[cid]['_week'] += 1
        week_num = courses_history[cid]['_week']

        st = stats_by_session.get(session.id, {'generated': 0, 'used': 0, 'given': 0})
        generated = st['generated']
        used      = st['used']
        given     = st['given']
        pending   = generated - used - given if generated else 0
        coverage  = round(used / generated * 100) if generated else 0
        enrolled  = student_counts.get(cid, 0)

        courses_history[cid]['sessions'].append({
            'week_num': week_num,
            'session':  session,
            'enrolled': enrolled,
            'generated': generated,
            'used':      used,
            'given':     given,
            'pending':   max(pending, 0),
            'coverage':  coverage,
        })

        total_generated += generated
        total_used      += used

    total_sessions = sum(len(c['sessions']) for c in courses_history.values())
    overall_coverage = round(total_used / total_generated * 100) if total_generated else 0

    return render(request, 'attendance/ta_history.html', {
        'ta_profile':      ta_profile,
        'courses_history': courses_history,
        'total_sessions':  total_sessions,
        'total_generated': total_generated,
        'total_used':      total_used,
        'overall_coverage': overall_coverage,
    })


@login_required
def ta_add_levels(request):
    """Let a TA add more levels to their assigned levels."""
    if not hasattr(request.user, 'taprofile'):
        return redirect('attendance:dashboard')

    ta_profile = request.user.taprofile
    all_levels = Level.objects.all().order_by('name')

    if request.method == 'POST':
        selected_ids = request.POST.getlist('levels')
        # Set assigned_levels to the full new selection
        ta_profile.assigned_levels.set(Level.objects.filter(id__in=selected_ids))
        messages.success(request, 'Your assigned levels have been updated.')
        return redirect('attendance:ta_dashboard')

    assigned_ids = set(ta_profile.assigned_levels.values_list('id', flat=True))
    return render(request, 'attendance/ta_add_levels.html', {
        'ta_profile':    ta_profile,
        'all_levels':    all_levels,
        'assigned_ids':  assigned_ids,
    })


@login_required
def ta_dashboard(request):
    """TA dashboard - show assigned courses and sessions with students"""
    try:
        ta_profile = TAProfile.objects.get(user=request.user)
    except TAProfile.DoesNotExist:
        messages.error(request, "TA profile not found. Please contact admin.")
        return redirect('/')

    # Check if TA is approved
    if not ta_profile.is_approved:
        messages.error(request, "Your account is pending admin approval. You will be notified via email once approved.")
        return redirect('login')

    assigned_levels = ta_profile.assigned_levels.all()
    assigned_level_ids = [level.id for level in assigned_levels]
    
    # Get sessions for TA's assigned levels — only from active (non-turned-off) semesters
    sessions = ClassSession.objects.filter(
        course__level__id__in=assigned_level_ids,
        course__semester__is_active=True,
    ).order_by('course__level', 'course__code', 'date').select_related('course')

    # Students who have actually registered for courses in this TA's levels (active semesters only)
    courses_in_levels = Course.objects.filter(level__in=assigned_levels, semester__is_active=True)
    total_students_count = UserProfile.objects.filter(
        registered_courses__in=courses_in_levels
    ).distinct().count()

    # Cache per-course registered student counts to avoid N queries in the loop
    course_student_counts = {
        course.id: UserProfile.objects.filter(registered_courses=course).count()
        for course in courses_in_levels
    }

    # Group sessions by course
    sessions_by_course = {}

    for session in sessions:
        course_key = session.course.id
        student_count = course_student_counts.get(course_key, 0)

        if course_key not in sessions_by_course:
            sessions_by_course[course_key] = {
                'course': session.course,
                'sessions': []
            }

        sessions_by_course[course_key]['sessions'].append({
            'id': session.id,
            'date': session.date,
            'start_time': session.start_time,
            'end_time': session.end_time,
            'topic': session.topic,
            'student_count': student_count,
        })
    
    # Get statistics
    total_codes_generated = TACode.objects.filter(ta=request.user).count()
    total_codes_used = TACode.objects.filter(ta=request.user, is_used=True).count()
    
    context = {
        'ta_profile': ta_profile,
        'sessions_by_course': sessions_by_course,
        'total_codes_generated': total_codes_generated,
        'total_codes_used': total_codes_used,
        'total_students': total_students_count,
        'assigned_levels': assigned_levels,
    }
    return render(request, 'attendance/ta_dashboard.html', context)


@login_required
@require_POST
def ta_generate_code(request):
    """TA generates a unique code for a specific student and session"""
    session_id = request.POST.get('session_id')
    student_username = request.POST.get('student_username')
    
    session = get_object_or_404(ClassSession, id=session_id)
    
    try:
        student = User.objects.get(username=student_username)
    except User.DoesNotExist:
        return JsonResponse({"error": f"Student '{student_username}' not found"}, status=400)
    
    # Check if student has a profile
    try:
        student_profile = student.userprofile
    except UserProfile.DoesNotExist:
        return JsonResponse({"error": "Student profile not found"}, status=400)
    
    # Check if TA is authorized and approved for this student's level
    try:
        ta_profile = TAProfile.objects.get(user=request.user)
        if not ta_profile.is_approved:
            return JsonResponse({"error": "Your TA account is pending approval."}, status=403)
        if student_profile.level not in ta_profile.assigned_levels.all():
            return JsonResponse({"error": f"You are not authorized for Level {student_profile.level.name}"}, status=403)
    except TAProfile.DoesNotExist:
        return JsonResponse({"error": "TA profile not found"}, status=403)
    
    # Check if code already exists for this student/session
    existing = TACode.objects.filter(student=student, class_session=session).first()
    if existing:
        if existing.is_used:
            return JsonResponse({"error": f"Code already used by {student.username}"}, status=400)
        else:
            return JsonResponse({
                "code": existing.code,
                "student": student.username,
                "warning": "Code already exists for this student",
                "existing": True
            })
    
    # Generate unique 2-5 digit code
    import random
    while True:
        code_length = random.choice([2, 3, 4, 5])
        code = ''.join([str(random.randint(0, 9)) for _ in range(code_length)])
        if not TACode.objects.filter(code=code, class_session=session).exists():
            break
    
    ta_code = TACode.objects.create(
        code=code,
        student=student,
        class_session=session,
        ta=request.user
    )
    
    return JsonResponse({
        "code": ta_code.code,
        "student": student.username,
        "session_id": session.id
    })


@login_required
@require_POST
def ta_generate_all_codes(request):
    """TA generates unique codes for ALL students in a session at once"""
    session_id = request.POST.get('session_id')
    session = get_object_or_404(ClassSession, id=session_id)
    
    # Check if TA is authorized and approved
    try:
        ta_profile = TAProfile.objects.get(user=request.user)
    except TAProfile.DoesNotExist:
        return JsonResponse({"error": "TA profile not found"}, status=403)

    if not ta_profile.is_approved:
        return JsonResponse({"error": "Your TA account is pending approval."}, status=403)

    # Get all students for this session's course level
    students = UserProfile.objects.filter(level=session.course.level).select_related('user')
    
    generated_count = 0
    skipped_count = 0
    
    import random
    
    for student_profile in students:
        # Check if code already exists
        existing = TACode.objects.filter(student=student_profile.user, class_session=session).first()
        if existing:
            if existing.is_used:
                skipped_count += 1
            continue
        
        # Generate unique code
        while True:
            code_length = random.choice([2, 3, 4, 5])
            code = ''.join([str(random.randint(0, 9)) for _ in range(code_length)])
            if not TACode.objects.filter(code=code, class_session=session).exists():
                break
        
        TACode.objects.create(
            code=code,
            student=student_profile.user,
            class_session=session,
            ta=request.user
        )
        generated_count += 1
    
    return JsonResponse({
        "success": True,
        "generated": generated_count,
        "skipped": skipped_count,
        "message": f"Generated {generated_count} codes, {skipped_count} already had codes"
    })


@login_required
@require_POST
def ta_mark_distributed(request, code_id):
    """TA marks that code has been given to student"""
    ta_code = get_object_or_404(TACode, id=code_id, ta=request.user)
    ta_code.is_distributed = True
    ta_code.distributed_at = timezone.now()
    ta_code.save()
    messages.success(request, f"Code {ta_code.code} marked as given to {ta_code.student.username}")
    return redirect('attendance:ta_dashboard')


@login_required
@require_POST
def student_submit_ta_code(request):
    """Student submits the code given by TA"""
    session_id = request.POST.get('session_id')
    entered_code = request.POST.get('code', '').strip()
    
    session = get_object_or_404(ClassSession, id=session_id)
    
    # Check if student already submitted
    if AttendanceRecord.objects.filter(student=request.user, class_session=session).exists():
        return JsonResponse({"error": "You have already submitted attendance for this session."}, status=400)
    
    # Find the code
    try:
        ta_code = TACode.objects.get(code=entered_code, class_session=session)
    except TACode.DoesNotExist:
        return JsonResponse({"error": "Invalid code. Please check with your TA."}, status=400)
    
    # Check if code belongs to this student
    if ta_code.student != request.user:
        CodeMisuseAlert.objects.create(
            code=None,
            attempted_by=request.user,
            reason=f"Student {request.user.username} tried to use code belonging to {ta_code.student.username}"
        )
        return JsonResponse({"error": "This code belongs to another student."}, status=400)
    
    # Check if code already used
    if ta_code.is_used:
        return JsonResponse({"error": "This code has already been used."}, status=400)
    
    # Mark code as used
    ta_code.is_used = True
    ta_code.used_at = timezone.now()
    ta_code.save()
    
    # Also mark as distributed automatically when submitted
    if not ta_code.is_distributed:
        ta_code.is_distributed = True
        ta_code.distributed_at = timezone.now()
        ta_code.save()
    
    # Create attendance record
    dummy_code = AttendanceCode.objects.create(
        student=request.user,
        class_session=session,
        code_string=f"TA-{ta_code.code}",
    )
    
    AttendanceRecord.objects.create(
        student=request.user,
        class_session=session,
        code=dummy_code,
        submitted_at=timezone.now()
    )
    
    return JsonResponse({"success": True, "message": "Attendance submitted successfully!"})


# ── AJAX: Get Students for TA Dashboard (PAGINATED) ──────────────────────────

@login_required
def ta_get_students_ajax(request):
    """AJAX endpoint to get paginated students for a session"""
    session_id = request.GET.get('session_id')
    page = request.GET.get('page', 1)
    search = request.GET.get('search', '')
    status_filter = request.GET.get('status', 'all')
    
    session = get_object_or_404(ClassSession, id=session_id)
    
    # Get all students for this course level
    students = UserProfile.objects.filter(level=session.course.level).select_related('user')
    
    # Apply search filter
    if search:
        students = students.filter(
            Q(user__first_name__icontains=search) |
            Q(user__last_name__icontains=search) |
            Q(user__username__icontains=search) |
            Q(student_id_number__icontains=search)
        )
    
    # Get existing codes for this session for THIS TA only
    existing_codes = {}
    ta_codes = TACode.objects.filter(
        class_session=session,
        ta=request.user
    ).select_related('student')
    
    for code in ta_codes:
        existing_codes[code.student_id] = code
    
    # Build student data with their codes
    student_list = []
    for student in students:
        code = existing_codes.get(student.user.id)
        
        # Determine status for filtering
        student_status = 'pending'
        if code:
            if code.is_used:
                student_status = 'used'
            elif code.is_distributed:
                student_status = 'given'
        
        # Apply status filter
        if status_filter != 'all' and student_status != status_filter:
            continue
        
        student_list.append({
            'id': student.id,
            'username': student.user.username,
            'full_name': student.user.get_full_name() or student.user.username,
            'student_id': student.student_id_number or '-',
            'code': {
                'code_string': code.code if code else None,
                'is_used': code.is_used if code else False,
                'is_distributed': code.is_distributed if code else False,
                'id': code.id if code else None
            } if code else None,
            'status': student_status
        })
    
    # Paginate
    paginator = Paginator(student_list, 50)
    try:
        page_obj = paginator.page(page)
    except PageNotAnInteger:
        page_obj = paginator.page(1)
    except EmptyPage:
        page_obj = paginator.page(paginator.num_pages)
    
    return JsonResponse({
        'students': list(page_obj),
        'total': paginator.count,
        'page': page_obj.number,
        'total_pages': paginator.num_pages,
        'has_next': page_obj.has_next(),
        'has_previous': page_obj.has_previous(),
    })


# ── TA Change Password ───────────────────────────────────────────────────────

@login_required
def ta_change_password(request):
    if not hasattr(request.user, 'taprofile'):
        return redirect('attendance:dashboard')

    error = None
    if request.method == 'POST':
        current = request.POST.get('current_password', '')
        new_pw  = request.POST.get('new_password', '')
        confirm = request.POST.get('confirm_password', '')

        if not request.user.check_password(current):
            error = "Current password is incorrect."
        elif len(new_pw) < 8:
            error = "New password must be at least 8 characters."
        elif new_pw != confirm:
            error = "Passwords do not match."
        else:
            request.user.set_password(new_pw)
            request.user.save()
            from django.contrib.auth import update_session_auth_hash
            update_session_auth_hash(request, request.user)
            messages.success(request, "Password changed successfully!")
            return redirect('attendance:ta_dashboard')

    return render(request, 'attendance/ta_change_password.html', {'error': error})


# ── TA Session CSV Export ─────────────────────────────────────────────────────

@login_required
def ta_export_session_csv(request, session_id):
    if not hasattr(request.user, 'taprofile'):
        return redirect('attendance:dashboard')

    session = get_object_or_404(ClassSession, id=session_id)
    ta_profile = request.user.taprofile
    assigned_level_ids = list(ta_profile.assigned_levels.values_list('id', flat=True))

    if session.course.level_id not in assigned_level_ids:
        messages.error(request, 'You do not have access to this session.')
        return redirect('attendance:ta_dashboard')

    students = (
        UserProfile.objects
        .filter(registered_courses=session.course)
        .select_related('user')
        .order_by('user__first_name', 'user__last_name')
    )
    codes = TACode.objects.filter(class_session=session).select_related('student')
    code_by_student = {c.student_id: c for c in codes}

    response = HttpResponse(content_type='text/csv')
    safe_code = session.course.code.replace('/', '-')
    response['Content-Disposition'] = (
        f'attachment; filename="{safe_code}_Session_{session.date}.csv"'
    )

    writer = csv.writer(response)
    writer.writerow(['#', 'Student Name', 'Student ID', 'Code', 'Status'])

    for i, profile in enumerate(students, start=1):
        code = code_by_student.get(profile.user_id)
        if code:
            status   = 'Used' if code.is_used else ('Given' if code.is_distributed else 'Pending')
            code_val = code.code
        else:
            status   = 'No Code'
            code_val = ''

        writer.writerow([
            i,
            profile.user.get_full_name() or profile.user.username,
            profile.student_id_number or profile.user.username,
            code_val,
            status,
        ])

    return response


# ── Student Guide ────────────────────────────────────────────────────────────

def student_guide(request):
    """Display student guide page"""
    return render(request, 'attendance/student_guide.html')


# ── TA Guide ──────────────────────────────────────────────────────────────────

@login_required
def ta_guide(request):
    if not hasattr(request.user, 'taprofile'):
        return redirect('attendance:dashboard')
    return render(request, 'attendance/ta_guide.html')


# ── TA Announcements ──────────────────────────────────────────────────────────

@login_required
def ta_announcements(request):
    if not hasattr(request.user, 'taprofile'):
        return redirect('attendance:dashboard')

    ta_profile = request.user.taprofile
    if not ta_profile.is_approved:
        return redirect('attendance:ta_dashboard')

    assigned_levels = ta_profile.assigned_levels.all()
    past = TAnnouncement.objects.filter(ta=request.user).prefetch_related('target_levels')

    if request.method == 'POST':
        title   = request.POST.get('title', '').strip()
        body    = request.POST.get('message', '').strip()
        lv_ids  = request.POST.getlist('levels')

        if not title or not body:
            messages.error(request, 'Both a title and a message are required.')
        else:
            target_levels = (
                Level.objects.filter(id__in=lv_ids)
                if lv_ids
                else assigned_levels
            )
            courses = Course.objects.filter(
                level__in=target_levels,
                semester__is_active=True,
            )
            students = (
                UserProfile.objects
                .filter(registered_courses__in=courses, user__is_active=True)
                .distinct()
                .select_related('user')
            )

            ta_name = request.user.get_full_name() or request.user.username
            sent_count = 0
            for profile in students:
                if profile.user.email:
                    try:
                        html_body = render_to_string(
                            'attendance/announcement_email.html',
                            {
                                'ta_name':      ta_name,
                                'title':        title,
                                'message':      body,
                                'student_name': profile.user.get_full_name() or profile.user.username,
                            },
                        )
                        send_mail(
                            subject=f'[SWASA] {title}',
                            message=strip_tags(html_body),
                            from_email='noreply@swasa.edu.gh',
                            recipient_list=[profile.user.email],
                            html_message=html_body,
                            fail_silently=True,
                        )
                        sent_count += 1
                    except Exception:
                        pass

            ann = TAnnouncement.objects.create(
                ta=request.user,
                title=title,
                message=body,
                recipient_count=sent_count,
            )
            ann.target_levels.set(target_levels)

            messages.success(
                request,
                f'Announcement sent to {sent_count} student{"s" if sent_count != 1 else ""}.'
            )
            return redirect('attendance:ta_announcements')

    return render(request, 'attendance/ta_announcements.html', {
        'ta_profile':      ta_profile,
        'assigned_levels': assigned_levels,
        'past':            past,
    })


# ── Force Password Change ─────────────────────────────────────────────────────

@login_required
def change_password(request):
    profile = get_profile(request.user)
    if profile and not profile.must_change_password:
        return redirect('attendance:dashboard')

    error = None
    if request.method == 'POST':
        new_password = request.POST.get('new_password', '')
        confirm_password = request.POST.get('confirm_password', '')

        if len(new_password) < 8:
            error = "Password must be at least 8 characters."
        elif new_password == request.user.username:
            error = "Your password cannot be the same as your Student ID."
        elif new_password != confirm_password:
            error = "Passwords do not match."
        else:
            request.user.set_password(new_password)
            request.user.save()
            if profile:
                profile.must_change_password = False
                profile.save()
            from django.contrib.auth import update_session_auth_hash
            update_session_auth_hash(request, request.user)
            messages.success(request, "Password changed successfully!")
            return redirect('attendance:dashboard')

    return render(request, 'attendance/change_password.html', {'error': error})