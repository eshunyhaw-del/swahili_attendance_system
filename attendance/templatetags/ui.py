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
