import jwt
from django.conf import settings
from django.contrib.auth.models import User
from django.shortcuts import redirect
from django.urls import reverse


class JWTAuthMiddleware:
    """Authenticate requests using a JWT stored in an httpOnly cookie."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if not request.user.is_authenticated:
            token = request.COOKIES.get('access_token')
            if token:
                try:
                    payload = jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=['HS256'])
                    user = User.objects.get(id=payload['user_id'], is_active=True)
                    request.user = user
                except (jwt.InvalidTokenError, User.DoesNotExist, KeyError):
                    pass

        return self.get_response(request)


EXEMPT_URLS = {
    reverse('attendance:change_password'),
    reverse('login'),
    reverse('logout'),
}


class ForcePasswordChangeMiddleware:
    """Redirect students who still need to set a password (legacy accounts)."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if (
            request.user.is_authenticated
            and not request.user.is_staff
            and not hasattr(request.user, 'taprofile')
            and request.path not in EXEMPT_URLS
            and not request.path.startswith('/admin/')
            and not request.path.startswith('/api/')
        ):
            try:
                profile = request.user.userprofile
                if profile.must_change_password:
                    return redirect('attendance:change_password')
            except Exception:
                pass

        return self.get_response(request)
