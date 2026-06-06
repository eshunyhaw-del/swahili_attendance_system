from django.shortcuts import redirect
from django.urls import reverse


EXEMPT_URLS = {
    reverse('attendance:change_password'),
    reverse('login'),
    reverse('logout'),
}


class ForcePasswordChangeMiddleware:
    """Redirect students to change their password on first login."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if (
            request.user.is_authenticated
            and not request.user.is_staff
            and not hasattr(request.user, 'taprofile')
            and request.path not in EXEMPT_URLS
            and not request.path.startswith('/admin/')
        ):
            try:
                profile = request.user.userprofile
                if profile.must_change_password:
                    return redirect('attendance:change_password')
            except Exception:
                pass

        return self.get_response(request)
