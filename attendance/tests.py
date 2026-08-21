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
