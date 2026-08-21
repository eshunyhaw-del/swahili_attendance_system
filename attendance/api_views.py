import secrets

from django.contrib.auth.models import User
from django.core.cache import cache
from django.core.mail import send_mail
from django.utils import timezone
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken

from .api_serializers import (
    LoginRequestSerializer,
    PasswordResetConfirmSerializer,
    PasswordResetRequestSerializer,
    VerifyOTPSerializer,
)
from .models import OTPCode

_OTP_SENT_MSG = "If that email is registered, an OTP has been sent."

# Account-level brute-force lock: after this many bad guesses for a given
# (user, purpose), all outstanding OTPs are invalidated so the attacker must
# trigger a fresh send. This is keyed to the account, so it holds even if the
# attacker rotates source IPs (which per-IP throttling alone would not stop).
_MAX_OTP_ATTEMPTS = 5
_OTP_ATTEMPT_TTL = 300  # seconds


def _attempts_key(user, purpose):
    return f"api_otp_attempts_{user.id}_{purpose}"


def _register_failed_attempt(user, purpose):
    """Count a failed OTP guess. When the cap is hit, burn outstanding OTPs.

    Returns True if the account is now locked (caller should tell the user to
    request a new code), else False.
    """
    key = _attempts_key(user, purpose)
    attempts = cache.get(key, 0) + 1
    if attempts >= _MAX_OTP_ATTEMPTS:
        OTPCode.objects.filter(user=user, purpose=purpose, is_used=False).update(is_used=True)
        cache.delete(key)
        return True
    cache.set(key, attempts, _OTP_ATTEMPT_TTL)
    return False


def _clear_failed_attempts(user, purpose):
    cache.delete(_attempts_key(user, purpose))


def _generate_otp():
    return f"{secrets.randbelow(1000000):06d}"


def _invalidate_previous_otps(user, purpose):
    OTPCode.objects.filter(user=user, purpose=purpose, is_used=False).update(is_used=True)


def _send_otp_email(user, otp, purpose):
    if purpose == OTPCode.PURPOSE_LOGIN:
        subject = "Your SWASA login OTP"
        body = (
            f"Hi {user.get_full_name() or user.username},\n\n"
            f"Your one-time login code is: {otp}\n\n"
            f"It expires in 5 minutes. Do not share it with anyone."
        )
    else:
        subject = "Your SWASA password reset OTP"
        body = (
            f"Hi {user.get_full_name() or user.username},\n\n"
            f"Your password reset code is: {otp}\n\n"
            f"It expires in 5 minutes. If you did not request this, ignore this email."
        )

    send_mail(
        subject=subject,
        message=body,
        from_email=None,  # uses DEFAULT_FROM_EMAIL
        recipient_list=[user.email],
        fail_silently=False,
    )


def _get_user_by_email(email):
    try:
        return User.objects.get(email__iexact=email, is_active=True)
    except User.DoesNotExist:
        return None


class LoginRequestView(APIView):
    """POST /api/auth/login/ — send a 6-digit OTP to the user's email."""

    permission_classes = [AllowAny]
    throttle_scope = 'otp_request'

    def post(self, request):
        serializer = LoginRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        email = serializer.validated_data['email']
        user = _get_user_by_email(email)

        if user:
            otp = _generate_otp()
            _invalidate_previous_otps(user, OTPCode.PURPOSE_LOGIN)
            OTPCode.objects.create(user=user, code=otp, purpose=OTPCode.PURPOSE_LOGIN)
            try:
                _send_otp_email(user, otp, OTPCode.PURPOSE_LOGIN)
            except Exception:
                return Response(
                    {"detail": "Failed to send OTP email. Please try again later."},
                    status=status.HTTP_503_SERVICE_UNAVAILABLE,
                )

        return Response({"detail": _OTP_SENT_MSG}, status=status.HTTP_200_OK)


class VerifyOTPView(APIView):
    """POST /api/auth/verify-otp/ — verify OTP and return JWT tokens."""

    permission_classes = [AllowAny]
    throttle_scope = 'otp_verify'

    def post(self, request):
        serializer = VerifyOTPSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        email = serializer.validated_data['email']
        entered_otp = serializer.validated_data['otp']

        user = _get_user_by_email(email)
        if not user:
            return Response(
                {"detail": "Invalid OTP or email."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        otp_obj = (
            OTPCode.objects.filter(
                user=user,
                purpose=OTPCode.PURPOSE_LOGIN,
                is_used=False,
                code=entered_otp,
            )
            .order_by('-created_at')
            .first()
        )

        if not otp_obj or otp_obj.is_expired():
            locked = _register_failed_attempt(user, OTPCode.PURPOSE_LOGIN)
            detail = (
                "Too many failed attempts. Please request a new code."
                if locked else "Invalid or expired OTP."
            )
            return Response({"detail": detail}, status=status.HTTP_400_BAD_REQUEST)

        otp_obj.is_used = True
        otp_obj.save(update_fields=['is_used'])
        _clear_failed_attempts(user, OTPCode.PURPOSE_LOGIN)

        refresh = RefreshToken.for_user(user)
        return Response(
            {
                "access": str(refresh.access_token),
                "refresh": str(refresh),
                "user": {
                    "id": user.id,
                    "username": user.username,
                    "email": user.email,
                    "full_name": user.get_full_name(),
                },
            },
            status=status.HTTP_200_OK,
        )


class PasswordResetRequestView(APIView):
    """POST /api/auth/password-reset/ — send a password-reset OTP."""

    permission_classes = [AllowAny]
    throttle_scope = 'otp_request'

    def post(self, request):
        serializer = PasswordResetRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        email = serializer.validated_data['email']
        user = _get_user_by_email(email)

        if user:
            otp = _generate_otp()
            _invalidate_previous_otps(user, OTPCode.PURPOSE_PASSWORD_RESET)
            OTPCode.objects.create(user=user, code=otp, purpose=OTPCode.PURPOSE_PASSWORD_RESET)
            try:
                _send_otp_email(user, otp, OTPCode.PURPOSE_PASSWORD_RESET)
            except Exception:
                return Response(
                    {"detail": "Failed to send OTP email. Please try again later."},
                    status=status.HTTP_503_SERVICE_UNAVAILABLE,
                )

        return Response({"detail": _OTP_SENT_MSG}, status=status.HTTP_200_OK)


class PasswordResetConfirmView(APIView):
    """POST /api/auth/password-reset/confirm/ — verify OTP and set new password."""

    permission_classes = [AllowAny]
    throttle_scope = 'otp_verify'

    def post(self, request):
        serializer = PasswordResetConfirmSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        email = serializer.validated_data['email']
        entered_otp = serializer.validated_data['otp']
        new_password = serializer.validated_data['new_password']

        user = _get_user_by_email(email)
        if not user:
            return Response(
                {"detail": "Invalid OTP or email."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        otp_obj = (
            OTPCode.objects.filter(
                user=user,
                purpose=OTPCode.PURPOSE_PASSWORD_RESET,
                is_used=False,
                code=entered_otp,
            )
            .order_by('-created_at')
            .first()
        )

        if not otp_obj or otp_obj.is_expired():
            locked = _register_failed_attempt(user, OTPCode.PURPOSE_PASSWORD_RESET)
            detail = (
                "Too many failed attempts. Please request a new code."
                if locked else "Invalid or expired OTP."
            )
            return Response({"detail": detail}, status=status.HTTP_400_BAD_REQUEST)

        otp_obj.is_used = True
        otp_obj.save(update_fields=['is_used'])
        _clear_failed_attempts(user, OTPCode.PURPOSE_PASSWORD_RESET)

        user.set_password(new_password)
        user.save(update_fields=['password'])

        # Clear the must_change_password flag if set
        try:
            profile = user.userprofile
            if profile.must_change_password:
                profile.must_change_password = False
                profile.save(update_fields=['must_change_password'])
        except Exception:
            pass

        return Response(
            {"detail": "Password has been reset successfully."},
            status=status.HTTP_200_OK,
        )
