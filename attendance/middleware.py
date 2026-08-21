from django.contrib.auth.models import User
from django.shortcuts import redirect
from django.urls import reverse

from .tokens import (
    decode_token,
    make_access_token,
    set_access_cookie,
    user_security_hash,
)


class JWTAuthMiddleware:
    """Authenticate requests from the JWT access-token cookie.

    Adds two things over a plain decode:
      * Password-bound revocation — a token whose `sh` claim no longer matches
        the user's current password hash is rejected (covers password
        change/reset).
      * Sliding refresh — if the (short-lived) access token is missing/expired
        but a valid refresh-token cookie is present, a fresh access token is
        minted and set on the response, so users are not logged out every couple
        of hours.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        new_access_token = None
        if not request.user.is_authenticated:
            user, new_access_token = self._authenticate(request)
            if user is not None:
                request.user = user

        response = self.get_response(request)

        if new_access_token:
            set_access_cookie(response, new_access_token)
        return response

    def _user_for(self, payload):
        """Resolve and revocation-check the user named in a token payload."""
        try:
            user = User.objects.get(id=payload['user_id'], is_active=True)
        except (User.DoesNotExist, KeyError):
            return None
        sh = payload.get('sh')
        # Reject if the security hash is present but no longer matches (password
        # changed). Tokens minted before this feature have no `sh` and are
        # grandfathered until they expire.
        if sh is not None and sh != user_security_hash(user):
            return None
        return user

    def _authenticate(self, request):
        """Return (user, new_access_token_or_None)."""
        access = request.COOKIES.get('access_token')
        if access:
            payload = decode_token(access, 'access')
            if payload:
                user = self._user_for(payload)
                if user is not None:
                    return user, None

        # Access token missing or invalid — try the refresh token.
        refresh = request.COOKIES.get('refresh_token')
        if refresh:
            payload = decode_token(refresh, 'refresh')
            if payload:
                user = self._user_for(payload)
                if user is not None:
                    return user, make_access_token(user)

        return None, None


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
