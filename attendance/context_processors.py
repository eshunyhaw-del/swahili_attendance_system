from datetime import datetime, time, timedelta

from django.conf import settings
from django.core.cache import cache
from django.utils import timezone

from .models import (
    CulturalDate, Notification, StudentNotification, SystemNotification, Semester,
)


def alumni_invite(request):
    """Show the alumni WhatsApp invite pop-up to Level 400 students and TAs during
    the final days of the active SECOND semester.

    The window is [end_date - ALUMNI_INVITE_WINDOW_DAYS, end_date]. The template
    shows it once per browser session (so it reappears each time they open the
    app, but not on every page navigation)."""
    user = getattr(request, 'user', None)
    if not user or not user.is_authenticated:
        return {}

    # Audience: approved TAs, or Level 400 students (never lecturers/admins).
    is_ta = hasattr(user, 'taprofile') and getattr(user.taprofile, 'is_approved', False)
    is_level_400 = False
    if not is_ta and not user.is_staff:
        profile = getattr(user, 'userprofile', None)
        is_level_400 = bool(profile and profile.level and profile.level.name == '400')
    if not (is_ta or is_level_400):
        return {}

    # Timing: active, non-archived SECOND semester, within the closing window.
    semester = Semester.objects.filter(is_active=True, is_archived=False).first()
    if not semester or 'second' not in (semester.name or '').lower():
        return {}
    window_days = getattr(settings, 'ALUMNI_INVITE_WINDOW_DAYS', 7)
    today = timezone.localdate()
    if not (semester.end_date - timedelta(days=window_days) <= today <= semester.end_date):
        return {}

    return {
        'show_alumni_popup': True,
        'alumni_whatsapp_url': getattr(settings, 'ALUMNI_WHATSAPP_URL', ''),
    }


def _create_cultural_notifications(user, today, cultural_dates):
    """Create one SystemNotification per cultural date per user per day (idempotent via cache)."""
    cache_key = f"cult_notif_{user.id}_{today.isoformat()}"
    if cache.get(cache_key):
        return

    if cultural_dates:
        today_start = timezone.make_aware(datetime.combine(today, time.min))
        existing_titles = set(
            SystemNotification.objects.filter(
                user=user,
                notification_type=SystemNotification.TYPE_CULTURAL,
                created_at__gte=today_start,
            ).values_list('title', flat=True)
        )
        to_create = [
            SystemNotification(
                user=user,
                title=cd.name,
                message=cd.description,
                emoji=cd.emoji,
                notification_type=SystemNotification.TYPE_CULTURAL,
            )
            for cd in cultural_dates
            if cd.name not in existing_titles
        ]
        if to_create:
            SystemNotification.objects.bulk_create(to_create)

    # Cache for 12 hours; date-keyed so it resets after midnight automatically
    cache.set(cache_key, True, 43200)


def notifications(request):
    if not request.user.is_authenticated:
        return {}

    today = timezone.localdate()

    # Today's cultural dates (small table, fast query)
    today_cultural_dates = list(
        CulturalDate.objects.filter(day=today.day, month=today.month, is_active=True)
    )

    # Auto-create SystemNotifications for cultural dates (once per user per day)
    _create_cultural_notifications(request.user, today, today_cultural_dates)

    # Unread system notifications (all roles)
    sys_unread = list(
        SystemNotification.objects.filter(user=request.user, is_read=False)
        .order_by('-created_at')[:10]
    )

    if hasattr(request.user, 'taprofile') or request.user.is_staff:
        generic_unread = list(
            Notification.objects.filter(recipient=request.user, is_read=False)
            .order_by('-created_at')[:10]
        )
        ann_unread = []
        notif_type = 'generic'
    else:
        generic_unread = []
        ann_unread = list(
            StudentNotification.objects.filter(student=request.user, is_read=False)
            .select_related('announcement', 'announcement__course', 'announcement__ta')
            .order_by('-announcement__sent_at')[:10]
        )
        notif_type = 'announcement'

    total_unread = len(sys_unread) + len(ann_unread) + len(generic_unread)

    return {
        'sys_notifications':     sys_unread,
        'ann_notifications':     ann_unread,
        'generic_notifications': generic_unread,
        'unread_notif_count':    total_unread,
        'notif_type':            notif_type,
        'today_cultural_dates':  today_cultural_dates,
        # keep for templates that still reference unread_notifications directly
        'unread_notifications':  ann_unread if notif_type == 'announcement' else generic_unread,
    }
