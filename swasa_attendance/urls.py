from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from attendance.views import token_login_view, token_logout_view, otp_password_reset_request

urlpatterns = [
    path('admin/', admin.site.urls),

    # REST API — OTP auth
    path('api/auth/', include('attendance.api_urls')),

    # Auth
    path('login/', token_login_view, name='login'),
    path('logout/', token_logout_view, name='logout'),

    # Password reset — OTP-based (keeps the 'password_reset' name so the login page link works)
    path('password-reset/', otp_password_reset_request, name='password_reset'),

    # Attendance app
    path('', include('attendance.urls')),
]

# Serve static and media files during development
urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)