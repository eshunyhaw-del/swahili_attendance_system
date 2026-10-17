"""UI helpers for the SWASA design system.

{% load ui %}
{% icon "house" %}                 -> inline Lucide SVG (20px)
{% icon "clock" size=16 %}
{% icon "check" cls="text-ok" %}

Icons are read from static/icons/*.svg (Lucide, ISC licence) and inlined, so they
render with no network request and no JavaScript, and inherit the text colour.
"""
import re
from functools import lru_cache
from pathlib import Path

from django import template
from django.conf import settings
from django.utils.html import escape
from django.utils.safestring import mark_safe

register = template.Library()
_NAME = re.compile(r'^[a-z0-9-]+$')
_ICON_DIR = Path(settings.BASE_DIR) / 'static' / 'icons'


@lru_cache(maxsize=None)
def _body(name):
    path = _ICON_DIR / f'{name}.svg'
    svg = path.read_text(encoding='utf-8')
    inner = re.search(r'<svg[^>]*>(.*)</svg>', svg, re.S).group(1).strip()
    return re.sub(r'\s*\n\s*', ' ', inner)


@register.simple_tag
def icon(name, size=20, cls=''):
    if not _NAME.match(name) or not (_ICON_DIR / f'{name}.svg').exists():
        return ''
    return mark_safe(
        f'<svg class="icon {escape(cls)}" xmlns="http://www.w3.org/2000/svg" width="{int(size)}" '
        f'height="{int(size)}" viewBox="0 0 24 24" fill="none" stroke="currentColor" '
        f'stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" '
        f'focusable="false">{_body(name)}</svg>'
    )


# Status -> (visual variant, Lucide icon, default label). Only statuses the app
# actually supports, plus "upcoming" (a not-yet-held session, a display state).
_BADGES = {
    'present':      ('success', 'check',       'Present'),
    'absent':       ('danger',  'x',           'Absent'),
    'not_recorded': ('outline', 'minus',       'Not recorded'),
    'pending':      ('neutral', 'clock',       'Pending'),
    'eligible':     ('success', 'badge-check', 'Exam eligible'),
    'at_risk':      ('warning', 'badge-alert', 'At risk'),
    'not_eligible': ('danger',  'badge-x',     'Not eligible'),
    'upcoming':     ('neutral', 'clock',       'Upcoming'),
}


@register.simple_tag
def badge(status, label=None):
    """{% badge "present" %} / {% badge "present" label="Attendance recorded" %}

    A compact, informational status badge (icon + text, never colour alone)."""
    kind, icon_name, text = _BADGES.get(status, ('neutral', '', str(status)))
    glyph = icon(icon_name, 12) if icon_name else ''
    return mark_safe(f'<span class="ds-status ds-status-{kind}">{glyph}{escape(label or text)}</span>')
