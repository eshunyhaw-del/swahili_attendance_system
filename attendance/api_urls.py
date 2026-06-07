from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView

from .api_views import (
    LoginRequestView,
    PasswordResetConfirmView,
    PasswordResetRequestView,
    VerifyOTPView,
)

urlpatterns = [
    # Login via OTP
    path('login/', LoginRequestView.as_view(), name='api_login_request'),
    path('verify-otp/', VerifyOTPView.as_view(), name='api_verify_otp'),

    # Token refresh (standard simplejwt endpoint)
    path('token/refresh/', TokenRefreshView.as_view(), name='api_token_refresh'),

    # Password reset via OTP
    path('password-reset/', PasswordResetRequestView.as_view(), name='api_password_reset_request'),
    path('password-reset/confirm/', PasswordResetConfirmView.as_view(), name='api_password_reset_confirm'),
]
