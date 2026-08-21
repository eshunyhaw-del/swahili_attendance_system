"""Centralized JWT-cookie helpers for the custom web session.

All web-session tokens are minted here so their claims, lifetimes, and the
`secure` cookie flag stay consistent. Two security properties this module adds
over the previous inline `jwt.encode` calls:

  * Password-bound revocation. Every token carries a short `sh` claim derived
    (via HMAC) from the user's current password hash. Changing/resetting the
    password changes that hash, so all previously issued tokens stop validating
    immediately — real revocation for a stateless token.

  * Short access tokens + sliding refresh. The access token is short-lived; a
    longer-lived refresh token lets the middleware mint a fresh access token
    transparently, so shortening the access lifetime does not log users out.
"""

import hashlib
import hmac
from datetime import datetime, timedelta

import jwt
from django.conf import settings

# Lifetimes. Access is deliberately short; the refresh token (checked by the
# middleware) keeps the session alive without a 30-day bearer token floating
# around. "Remember me" only extends the refresh token.
ACCESS_TOKEN_TTL = timedelta(hours=2)
REFRESH_TOKEN_TTL = timedelta(days=7)
REFRESH_TOKEN_TTL_REMEMBER = timedelta(days=30)

_ALG = 'HS256'


def user_security_hash(user):
    """Short HMAC bound to the user's current password hash.

    Included in every token as the `sh` claim. When the password changes, this
    value changes, so tokens minted before the change fail validation.
    """
    key = settings.JWT_SECRET_KEY.encode()
    msg = (user.password or '').encode()
    return hmac.new(key, msg, hashlib.sha256).hexdigest()[:16]


def _encode(payload, ttl):
    now = datetime.utcnow()
    body = {**payload, 'iat': now, 'exp': now + ttl}
    return jwt.encode(body, settings.JWT_SECRET_KEY, algorithm=_ALG)


def make_access_token(user):
    return _encode({
        'user_id': user.id,
        'username': user.username,
        'type': 'access',
        'sh': user_security_hash(user),
    }, ACCESS_TOKEN_TTL)


def make_refresh_token(user, remember_me=False):
    ttl = REFRESH_TOKEN_TTL_REMEMBER if remember_me else REFRESH_TOKEN_TTL
    token = _encode({
        'user_id': user.id,
        'type': 'refresh',
        'sh': user_security_hash(user),
    }, ttl)
    return token, ttl


def _set_cookie(response, name, value, max_age):
    response.set_cookie(
        name, value,
        max_age=int(max_age),
        httponly=True,
        secure=settings.JWT_COOKIE_SECURE,
        samesite='Lax',
    )


def set_auth_cookies(response, user, remember_me=False):
    """Attach fresh access + refresh cookies for `user` to `response`."""
    access = make_access_token(user)
    refresh, refresh_ttl = make_refresh_token(user, remember_me)
    _set_cookie(response, 'access_token', access, ACCESS_TOKEN_TTL.total_seconds())
    _set_cookie(response, 'refresh_token', refresh, refresh_ttl.total_seconds())
    return response


def set_access_cookie(response, access_token):
    """Attach just a refreshed access cookie (used by the middleware)."""
    _set_cookie(response, 'access_token', access_token, ACCESS_TOKEN_TTL.total_seconds())
    return response


def decode_token(token, expected_type):
    """Return the payload if the token is valid AND of the expected type, else
    None. Signature/expiry errors are swallowed into None."""
    try:
        payload = jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[_ALG])
    except jwt.InvalidTokenError:
        return None
    # Older access tokens (pre-upgrade) have no 'type' claim; treat a missing
    # type as 'access' so existing sessions are not force-logged-out on deploy.
    token_type = payload.get('type', 'access')
    if token_type != expected_type:
        return None
    return payload
