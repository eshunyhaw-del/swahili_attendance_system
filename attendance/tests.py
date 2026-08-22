"""Security regression tests for the System_Redesigns hardening pass.

Covers:
  * C-1 — ta_get_students_ajax authorization (no PII/code leak to students)
  * C-2 — TA accounts are NOT auto-approved by email verification
  * C-3 — API OTP verification locks the account after repeated bad guesses
"""

from datetime import timedelta

from django.contrib.auth.models import User
from django.core.cache import cache
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from .models import (
    Course, ClassSession, Level, Semester, TAProfile, UserProfile, OTPCode,
)
from .tokens import make_access_token, make_refresh_token


def _make_semester():
    return Semester.objects.create(
        name="Test", year=2026,
        start_date="2026-01-01", end_date="2026-06-01",
        is_active=True,
    )


class TAGetStudentsAjaxAuthTests(TestCase):
    """C-1: only approved, correctly-assigned TAs (and admins) may read the
    session roster + TA codes."""

    def setUp(self):
        cache.clear()
        # Levels 100–400 are seeded by migration 0002, so get-or-create.
        self.level100, _ = Level.objects.get_or_create(name="100")
        self.level200, _ = Level.objects.get_or_create(name="200")
        semester = _make_semester()
        self.course = Course.objects.create(
            code="TEST 999", name="Intro", level=self.level100, semester=semester,
        )
        self.lecturer = User.objects.create_user("lect", password="x")
        self.session = ClassSession.objects.create(
            course=self.course, date=timezone.now().date(),
            topic="Week 1", lecturer=self.lecturer,
        )
        # A student at level 100
        self.student = User.objects.create_user("stud", password="x")
        UserProfile.objects.create(
            user=self.student, level=self.level100, student_id_number="10000001",
            must_change_password=False,
        )
        self.url = reverse("attendance:ta_get_students_ajax")

    def _get(self, user):
        self.client.force_login(user)
        return self.client.get(self.url, {"session_id": self.session.id})

    def test_student_is_denied(self):
        resp = self._get(self.student)
        self.assertEqual(resp.status_code, 403)

    def test_unapproved_ta_is_denied(self):
        ta_user = User.objects.create_user("ta_pending", password="x")
        ta = TAProfile.objects.create(user=ta_user, is_approved=False)
        ta.assigned_levels.add(self.level100)
        resp = self._get(ta_user)
        self.assertEqual(resp.status_code, 403)

    def test_wrong_level_ta_is_denied(self):
        ta_user = User.objects.create_user("ta_wrong", password="x")
        ta = TAProfile.objects.create(user=ta_user, is_approved=True)
        ta.assigned_levels.add(self.level200)  # not the session's level
        resp = self._get(ta_user)
        self.assertEqual(resp.status_code, 403)

    def test_approved_assigned_ta_is_allowed(self):
        ta_user = User.objects.create_user("ta_ok", password="x")
        ta = TAProfile.objects.create(user=ta_user, is_approved=True)
        ta.assigned_levels.add(self.level100)
        resp = self._get(ta_user)
        self.assertEqual(resp.status_code, 200)
        self.assertIn("students", resp.json())

    def test_admin_is_allowed(self):
        admin = User.objects.create_user("admin", password="x", is_staff=True)
        resp = self._get(admin)
        self.assertEqual(resp.status_code, 200)


class TACodeLengthTests(TestCase):
    """Medium #2: TA-generated codes are a fixed 6 digits (not the old 2–5)."""

    def setUp(self):
        cache.clear()
        self.level, _ = Level.objects.get_or_create(name='100')
        semester = _make_semester()
        self.course = Course.objects.create(
            code='TEST 998', name='Intro', level=self.level, semester=semester,
        )
        lecturer = User.objects.create_user('lect2', password='x')
        self.session = ClassSession.objects.create(
            course=self.course, date=timezone.now().date(),
            topic='W1', lecturer=lecturer,
        )
        self.student = User.objects.create_user('stud2', password='x')
        UserProfile.objects.create(
            user=self.student, level=self.level, student_id_number='20000002',
            must_change_password=False,
        )
        self.ta_user = User.objects.create_user('ta_ok2', password='x')
        ta = TAProfile.objects.create(user=self.ta_user, is_approved=True)
        ta.assigned_levels.add(self.level)

    def test_generated_code_is_six_digits(self):
        self.client.force_login(self.ta_user)
        resp = self.client.post(reverse('attendance:ta_generate_code'), {
            'session_id': self.session.id,
            'student_username': self.student.username,
        })
        self.assertEqual(resp.status_code, 200)
        code = resp.json()['code']
        self.assertEqual(len(code), 6)
        self.assertTrue(code.isdigit())


class TASelfApprovalTests(TestCase):
    """C-2: verifying an email must never flip a TA to approved."""

    def setUp(self):
        cache.clear()
        self.level, _ = Level.objects.get_or_create(name="100")

    def _make_pending_ta_with_magic_token(self):
        user = User.objects.create_user("ta_new", email="ta@x.com", password="x", is_active=False)
        ta = TAProfile.objects.create(user=user, is_approved=False)
        ta.assigned_levels.add(self.level)
        token = "11111111-1111-1111-1111-111111111111"
        OTPCode.objects.create(
            user=user, code="000000",
            purpose=OTPCode.PURPOSE_REGISTRATION,
            expires_at=timezone.now() + timedelta(minutes=10),
            magic_token=token,
            magic_token_expires_at=timezone.now() + timedelta(minutes=30),
        )
        return user, ta, token

    def test_magic_link_does_not_approve_ta(self):
        user, ta, token = self._make_pending_ta_with_magic_token()
        resp = self.client.get(
            reverse("attendance:magic_verify_registration", args=[token])
        )
        self.assertEqual(resp.status_code, 200)
        ta.refresh_from_db()
        user.refresh_from_db()
        self.assertFalse(ta.is_approved, "TA must remain unapproved after email verification")
        self.assertTrue(user.is_active, "email verification should still activate the account")
        # And no login token should have been handed out
        self.assertNotIn("access_token", resp.cookies)


class LoginRateLimitTests(TestCase):
    """H-4: repeated failed logins for the same email get rate-limited."""

    def setUp(self):
        cache.clear()
        self.url = reverse('login')

    def test_repeated_failures_are_throttled(self):
        # 5 wrong attempts for one email are allowed (each returns the generic
        # invalid-credentials page); the 6th is blocked with a throttle message.
        for _ in range(5):
            resp = self.client.post(self.url, {
                'email': 'nobody@example.com', 'password': 'wrong',
            })
            self.assertNotContains(resp, 'Too many failed sign-in attempts', status_code=200)

        resp = self.client.post(self.url, {
            'email': 'nobody@example.com', 'password': 'wrong',
        })
        self.assertContains(resp, 'Too many failed sign-in attempts', status_code=200)


class JWTSessionTests(TestCase):
    """H-2: JWT cookie auth — password-bound revocation and sliding refresh."""

    def setUp(self):
        cache.clear()
        level, _ = Level.objects.get_or_create(name='100')
        self.user = User.objects.create_user(
            'jwtuser', email='jwt@example.com', password='OldPass123', is_active=True,
        )
        UserProfile.objects.create(
            user=self.user, level=level, student_id_number='JWT001',
            must_change_password=False,
        )
        # A minimal login-required JSON endpoint (no template/profile gymnastics).
        self.url = reverse('attendance:notification_unread_count')

    def test_valid_access_token_authenticates(self):
        self.client.cookies['access_token'] = make_access_token(self.user)
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, 200)

    def test_password_change_revokes_existing_token(self):
        token = make_access_token(self.user)
        # Password change rotates the security hash → old token must stop working.
        self.user.set_password('NewPass456')
        self.user.save()
        self.client.cookies['access_token'] = token
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, 302)  # login_required redirect

    def test_refresh_token_mints_fresh_access_cookie(self):
        refresh, _ = make_refresh_token(self.user)
        self.client.cookies['refresh_token'] = refresh
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, 200)
        # Middleware should have issued a new access cookie from the refresh.
        self.assertIn('access_token', resp.cookies)
        self.assertTrue(resp.cookies['access_token'].value)


class APIOTPBruteForceTests(TestCase):
    """C-3: the API OTP verify endpoint must lock the account after repeated
    bad guesses instead of allowing unlimited attempts."""

    def setUp(self):
        cache.clear()
        self.user = User.objects.create_user(
            "otpuser", email="otp@x.com", password="x", is_active=True,
        )
        OTPCode.objects.create(
            user=self.user, code="123456",
            purpose=OTPCode.PURPOSE_LOGIN,
            expires_at=timezone.now() + timedelta(minutes=5),
        )
        self.url = reverse("api_verify_otp")

    def test_bad_guesses_lock_and_invalidate_otp(self):
        # 5 wrong guesses -> account lock + outstanding OTP invalidated
        for _ in range(5):
            resp = self.client.post(
                self.url, {"email": "otp@x.com", "otp": "000000"},
            )
            self.assertEqual(resp.status_code, 400)

        # The real OTP is now burned, so even the correct code must fail.
        resp = self.client.post(
            self.url, {"email": "otp@x.com", "otp": "123456"},
        )
        self.assertEqual(resp.status_code, 400)
        self.assertFalse(
            OTPCode.objects.filter(
                user=self.user, purpose=OTPCode.PURPOSE_LOGIN, is_used=False,
            ).exists(),
            "outstanding OTPs should be invalidated after the attempt cap",
        )


import tempfile
from django.test import override_settings


@override_settings(MEDIA_ROOT=tempfile.mkdtemp())
class ProfileEditTests(TestCase):
    """Profile editing for every role: name/email on User, photo/phone on Avatar."""

    def setUp(self):
        cache.clear()
        self.level100, _ = Level.objects.get_or_create(name="100")
        self.student = User.objects.create_user(
            "prof_stud", email="stud@example.com", password="x",
            first_name="Ama", last_name="Mensah",
        )
        UserProfile.objects.create(
            user=self.student, level=self.level100,
            student_id_number="20000001", must_change_password=False,
        )
        # Another account to test email-uniqueness collision.
        self.other = User.objects.create_user(
            "prof_other", email="taken@example.com", password="x",
        )
        self.url = reverse("attendance:profile")

    @staticmethod
    def _png_upload(name="pic.png"):
        from io import BytesIO
        from PIL import Image
        from django.core.files.uploadedfile import SimpleUploadedFile
        buf = BytesIO()
        Image.new("RGB", (4, 4), (13, 36, 114)).save(buf, format="PNG")
        return SimpleUploadedFile(name, buf.getvalue(), content_type="image/png")

    def test_get_requires_login(self):
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, 302)

    def test_get_renders_for_logged_in_user(self):
        self.client.force_login(self.student)
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, 200)
        # Avatar is lazily created on first visit.
        from .models import Avatar
        self.assertTrue(Avatar.objects.filter(user=self.student).exists())

    def test_updates_name_email_and_phone(self):
        self.client.force_login(self.student)
        resp = self.client.post(self.url, {
            "first_name": "Akosua", "last_name": "Boateng",
            "email": "new@example.com", "phone_number": "0241234567",
        })
        self.assertEqual(resp.status_code, 302)
        self.student.refresh_from_db()
        self.assertEqual(self.student.first_name, "Akosua")
        self.assertEqual(self.student.email, "new@example.com")
        self.assertEqual(self.student.avatar.phone_number, "0241234567")

    def test_duplicate_email_is_rejected(self):
        self.client.force_login(self.student)
        resp = self.client.post(self.url, {
            "first_name": "Ama", "last_name": "Mensah",
            "email": "TAKEN@example.com",  # case-insensitive clash with self.other
            "phone_number": "",
        })
        self.assertEqual(resp.status_code, 200)  # re-rendered with errors
        self.student.refresh_from_db()
        self.assertEqual(self.student.email, "stud@example.com")  # unchanged

    def test_photo_upload_saves_image(self):
        self.client.force_login(self.student)
        resp = self.client.post(self.url, {
            "first_name": "Ama", "last_name": "Mensah",
            "email": "stud@example.com", "phone_number": "",
            "image": self._png_upload(),
        })
        self.assertEqual(resp.status_code, 302)
        self.student.refresh_from_db()
        self.assertTrue(self.student.avatar.image)

    def test_lecturer_can_edit_profile(self):
        lecturer = User.objects.create_user("prof_lect", password="x", is_staff=True)
        self.client.force_login(lecturer)
        resp = self.client.post(self.url, {
            "first_name": "Kofi", "last_name": "Asante",
            "email": "lect@example.com", "phone_number": "0555555555",
        })
        self.assertEqual(resp.status_code, 302)
        lecturer.refresh_from_db()
        self.assertEqual(lecturer.first_name, "Kofi")
        self.assertEqual(lecturer.avatar.phone_number, "0555555555")


class AdminRecordsViewTests(TestCase):
    """Consolidated Meta-Ads-style records screen (student_attendance_report)."""

    def setUp(self):
        cache.clear()
        self.level100, _ = Level.objects.get_or_create(name="100")
        self.level200, _ = Level.objects.get_or_create(name="200")
        semester = _make_semester()
        self.course = Course.objects.create(
            code="REC 101", name="Records", level=self.level100, semester=semester,
        )
        self.session = ClassSession.objects.create(
            course=self.course, date=timezone.now().date(),
            topic="W1", lecturer=User.objects.create_user("rec_lect", password="x"),
        )
        # A level-100 student who attended the one session.
        self.stud_user = User.objects.create_user(
            "rec_stud", password="x", first_name="Nana", last_name="Owusu",
        )
        self.stud_profile = UserProfile.objects.create(
            user=self.stud_user, level=self.level100,
            student_id_number="30000001", must_change_password=False,
        )
        from .models import CourseRegistration, AttendanceRecord, AttendanceCode
        CourseRegistration.objects.create(user_profile=self.stud_profile, course=self.course)
        code = AttendanceCode.objects.create(
            student=self.stud_user, class_session=self.session, code_string="ABC12345",
        )
        AttendanceRecord.objects.create(
            student=self.stud_user, class_session=self.session, code=code,
        )

        self.staff = User.objects.create_user("rec_admin", password="x", is_staff=True)
        self.url = reverse("attendance:student_report")

    def test_non_staff_is_redirected(self):
        self.client.force_login(self.stud_user)
        resp = self.client.get(self.url)
        self.assertNotEqual(resp.status_code, 200)  # staff_member_required bounces

    def test_staff_sees_all_students_and_segments(self):
        self.client.force_login(self.staff)
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, 200)
        self.assertTemplateUsed(resp, "attendance/student_report.html")
        self.assertContains(resp, "Nana Owusu")
        # Level segments + opening summary present in context.
        seg_levels = {s['level'].name for s in resp.context['level_segments']}
        self.assertTrue({"100", "200"}.issubset(seg_levels))
        self.assertEqual(resp.context['active_level'], 'all')
        self.assertEqual(resp.context['summary_all']['count'], UserProfile.objects.count())

    def test_level_query_preselects_active_tab(self):
        self.client.force_login(self.staff)
        resp = self.client.get(self.url, {"level": self.level100.id})
        self.assertEqual(resp.context['active_level'], str(self.level100.id))

    def test_attended_student_is_on_track(self):
        self.client.force_login(self.staff)
        resp = self.client.get(self.url)
        row = next(s for s in resp.context['students'] if s['profile'].id == self.stud_profile.id)
        self.assertTrue(row['has_data'])
        self.assertFalse(row['at_risk'])
        self.assertEqual(row['attendance_percentage'], 100.0)


class SupportRoutingTests(TestCase):
    """A student support request goes to the level's TA first, with staff/admins
    always notified as a backup (and as the sole recipient when no TA covers the
    level)."""

    def setUp(self):
        cache.clear()
        self.level, _ = Level.objects.get_or_create(name="100")
        self.student = User.objects.create_user("sup_stud", password="x")
        UserProfile.objects.create(
            user=self.student, level=self.level,
            student_id_number="40000001", must_change_password=False,
        )
        self.ta = User.objects.create_user("sup_ta", password="x")
        tap = TAProfile.objects.create(user=self.ta, is_approved=True, is_active=True)
        tap.assigned_levels.add(self.level)
        self.admin = User.objects.create_user("sup_admin", password="x", is_staff=True)
        self.url = reverse("attendance:support")

    def test_ticket_notifies_both_ta_and_admin(self):
        from .models import Notification, SupportTicket
        self.client.force_login(self.student)
        resp = self.client.post(self.url, {"subject": "Cannot check in", "message": "The code won't work."})
        self.assertEqual(resp.status_code, 302)
        self.assertTrue(SupportTicket.objects.filter(student=self.student).exists())
        self.assertTrue(Notification.objects.filter(recipient=self.ta).exists(), "level TA should be notified")
        self.assertTrue(Notification.objects.filter(recipient=self.admin).exists(), "admin backup should be notified")

    def test_admin_notified_even_without_a_ta(self):
        from .models import Notification
        TAProfile.objects.all().delete()  # no TA covers the level
        self.client.force_login(self.student)
        self.client.post(self.url, {"subject": "Help", "message": "Test."})
        self.assertTrue(Notification.objects.filter(recipient=self.admin).exists(),
                        "admin should still receive tickets when no TA is assigned")


class StudentEmailDomainTests(TestCase):
    """New students may register only with an allowed email domain
    (settings.ALLOWED_STUDENT_EMAIL_DOMAINS — Gmail by default), because
    verification codes are Gmail-sent and reliably reach only those inboxes."""

    def _data(self, email):
        return {
            'full_name': 'Kwame Test', 'email': email,
            'student_id': '50000001', 'level': '100',
            'password': 'Str0ngPass!', 'password2': 'Str0ngPass!',
        }

    def _valid(self, email):
        from .forms import StudentRegistrationForm
        return StudentRegistrationForm(data=self._data(email)).is_valid()

    def test_student_email_is_blocked(self):
        self.assertFalse(self._valid('kwame@st.ug.edu.gh'))

    def test_other_providers_are_blocked(self):
        # Gmail-only default: institutional + other consumer providers blocked.
        for addr in ('kwame@yahoo.com', 'kwame@outlook.com', 'kwame@icloud.com', 'k@ug.edu.gh'):
            self.assertFalse(self._valid(addr), f"{addr} should be blocked")

    def test_gmail_is_allowed(self):
        self.assertTrue(self._valid('kwame@gmail.com'))

    def test_gmail_is_allowed_case_insensitive(self):
        self.assertTrue(self._valid('Kwame@GMAIL.com'))

    @override_settings(ALLOWED_STUDENT_EMAIL_DOMAINS=['gmail.com', 'yahoo.com'])
    def test_allowlist_is_configurable(self):
        # Broadening the setting lets another provider through without code change.
        self.assertTrue(self._valid('kwame@yahoo.com'))
        self.assertFalse(self._valid('kwame@outlook.com'))


class ExamEligibilityTests(TestCase):
    """Exam-eligibility rule: blocked if >=3 consecutive OR >=4 total absences
    in a course; 'warning' one short of either limit."""

    def _elig(self, statuses):
        from .views import exam_eligibility
        return exam_eligibility(statuses)

    def test_eligible_with_scattered_absences(self):
        r = self._elig(['present', 'absent', 'present', 'absent', 'present'])
        self.assertTrue(r['eligible'])
        self.assertEqual(r['status'], 'eligible')
        self.assertEqual(r['total_absent'], 2)
        self.assertEqual(r['max_consecutive_absent'], 1)

    def test_blocked_by_three_consecutive(self):
        r = self._elig(['present', 'absent', 'absent', 'absent', 'present'])
        self.assertFalse(r['eligible'])
        self.assertEqual(r['status'], 'blocked')
        self.assertEqual(r['max_consecutive_absent'], 3)

    def test_blocked_by_four_total(self):
        r = self._elig(['absent', 'present', 'absent', 'present', 'absent', 'present', 'absent'])
        self.assertFalse(r['eligible'])
        self.assertEqual(r['status'], 'blocked')
        self.assertEqual(r['total_absent'], 4)
        self.assertLess(r['max_consecutive_absent'], 3)  # blocked by total, not streak

    def test_warning_two_consecutive(self):
        r = self._elig(['present', 'absent', 'absent', 'present'])
        self.assertTrue(r['eligible'])
        self.assertEqual(r['status'], 'warning')

    def test_warning_three_total(self):
        r = self._elig(['absent', 'present', 'absent', 'present', 'absent'])
        self.assertTrue(r['eligible'])
        self.assertEqual(r['status'], 'warning')
        self.assertEqual(r['total_absent'], 3)

    def test_empty_is_eligible(self):
        r = self._elig([])
        self.assertTrue(r['eligible'])
        self.assertEqual(r['status'], 'eligible')


class AlumniInviteTests(TestCase):
    """Alumni pop-up shows to Level 400 students + approved TAs during the final
    ALUMNI_INVITE_WINDOW_DAYS of an active SECOND semester only."""

    def setUp(self):
        cache.clear()
        from .models import Semester
        Semester.objects.update(is_active=False)  # isolate from any seeded semester
        self.l400, _ = Level.objects.get_or_create(name='400')
        self.l100, _ = Level.objects.get_or_create(name='100')

    def _semester(self, name, days_to_end):
        from .models import Semester
        today = timezone.localdate()
        return Semester.objects.create(
            name=name, year=2026,
            start_date=today - timedelta(days=90),
            end_date=today + timedelta(days=days_to_end),
            is_active=True,
        )

    def _ctx(self, user):
        from django.test import RequestFactory
        from .context_processors import alumni_invite
        req = RequestFactory().get('/')
        req.user = user
        return alumni_invite(req)

    def _student(self, username, level):
        u = User.objects.create_user(username, password='x')
        UserProfile.objects.create(user=u, level=level, student_id_number=username[:8], must_change_password=False)
        return u

    def test_l400_student_in_window_sees_popup(self):
        self._semester('Second Semester', days_to_end=3)
        ctx = self._ctx(self._student('a400a', self.l400))
        self.assertTrue(ctx.get('show_alumni_popup'))
        self.assertIn('chat.whatsapp.com', ctx.get('alumni_whatsapp_url', ''))

    def test_approved_ta_in_window_sees_popup(self):
        self._semester('Second Semester', days_to_end=2)
        ta = User.objects.create_user('a_ta', password='x')
        TAProfile.objects.create(user=ta, is_approved=True)
        self.assertTrue(self._ctx(ta).get('show_alumni_popup'))

    def test_l100_student_does_not_see_popup(self):
        self._semester('Second Semester', days_to_end=3)
        self.assertFalse(self._ctx(self._student('a100a', self.l100)).get('show_alumni_popup'))

    def test_first_semester_does_not_show(self):
        self._semester('First Semester', days_to_end=3)
        self.assertFalse(self._ctx(self._student('a400b', self.l400)).get('show_alumni_popup'))

    def test_outside_window_does_not_show(self):
        self._semester('Second Semester', days_to_end=40)  # far from end
        self.assertFalse(self._ctx(self._student('a400c', self.l400)).get('show_alumni_popup'))

    def test_lecturer_does_not_see_popup(self):
        self._semester('Second Semester', days_to_end=3)
        lect = User.objects.create_user('a_lect', password='x', is_staff=True)
        self.assertFalse(self._ctx(lect).get('show_alumni_popup'))
