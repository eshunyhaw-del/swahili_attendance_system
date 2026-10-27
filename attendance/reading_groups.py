"""Reading groups: load a lecturer's group list and link names to student accounts."""

import re
from difflib import SequenceMatcher

from django.contrib.auth.models import User
from django.urls import reverse
from django.utils import timezone

from .models import (
    ReadingGroup, ReadingGroupMember, SystemNotification,
)


def _tokens(name):
    """Lower-case name parts. Hyphens split ("Abdul-Rahman" -> abdul, rahman);
    initials such as "G." or "M.Y." are dropped."""
    out = []
    for raw in re.split(r'[\s\-]+', (name or '').strip().lower()):
        if not raw or '.' in raw.strip('.'):
            continue                       # "m.y." style initials
        part = re.sub(r"[^a-z]", '', raw)  # drop apostrophes, dots, digits
        if len(part) > 1:
            out.append(part)
    return out


def _same(a, b):
    if a == b:
        return True
    return min(len(a), len(b)) >= 4 and SequenceMatcher(None, a, b).ratio() >= 0.84


def _covered(small, large):
    """How many tokens of `small` appear (allowing a small spelling slip) in `large`."""
    return sum(any(_same(t, u) for u in large) for t in small)


def match_user(listed_name, candidates):
    """Return (user, reason). `candidates` is an iterable of User.

    A name matches when every word of the shorter name appears in the longer one,
    in any order. A single-word listed name ("Juliet") only matches if exactly one
    student fits. Ties are refused, never guessed.
    """
    want = _tokens(listed_name)
    if not want:
        return None, 'empty name'
    best, best_score, tie = None, 0, False
    for user in candidates:
        have = _tokens(f"{user.first_name} {user.last_name}")
        if not have:
            continue
        small, large = (want, have) if len(want) <= len(have) else (have, want)
        if len(small) < 2 and len(want) >= 2:
            continue                       # the student's own name is a single word: too weak
        if _covered(small, large) < len(small):
            continue
        score = len(small) * 10 + len(large)
        if score > best_score:
            best, best_score, tie = user, score, False
        elif score == best_score:
            tie = True
    if best is None:
        return None, 'no registered student has that name'
    if tie:
        return None, 'more than one student fits this name'
    return best, 'matched'


def load_groups(course, groups):
    """Create or update groups/members from [(number, book, [names])] and link users.

    Re-runnable: a manually fixed link is kept, and unmatched names are tried again
    (more students register over time).
    Returns (report_lines, linked_count, unmatched_count).
    """
    candidates = list(
        User.objects.filter(
            is_active=True, is_staff=False, userprofile__isnull=False,
            userprofile__course_registrations__course=course,
            userprofile__course_registrations__is_active=True,
        ).distinct()
    )
    lines, linked, unmatched = [f"{len(candidates)} active registrants in {course.code}"], 0, 0
    for number, book, names in groups:
        group, _ = ReadingGroup.objects.update_or_create(
            course=course, number=number, defaults={'book': book})
        lines.append(f"Group {number}: {book}")
        for name in names:
            member, _ = ReadingGroupMember.objects.get_or_create(group=group, listed_name=name)
            if member.user_id is None:
                user, why = match_user(name, candidates)
                if user:
                    member.user = user
                    member.save(update_fields=['user'])
            else:
                user, why = member.user, 'already linked'
            if user:
                linked += 1
                lines.append(f"   OK        {name}  ->  {user.get_full_name()} <{user.email}> ({why})")
            else:
                unmatched += 1
                lines.append(f"   NOT FOUND {name}  ({why})")
    return lines, linked, unmatched


def notify_members(course):
    """Send each newly linked student one notification. Returns how many were sent."""
    sent = 0
    for m in ReadingGroupMember.objects.filter(
            group__course=course, user__isnull=False, notified_at__isnull=True
    ).select_related('group', 'user'):
        SystemNotification.objects.create(
            user=m.user,
            title=f"{course.code}: your reading group",
            message=(
                f"Find the group assignments and set books for {course.name}. "
                f"You are in Group {m.group.number} and your book is {m.group.book}. "
                f"Open the page to see your group mates."
            ),
            emoji='\U0001F4DA',
            link=reverse('attendance:reading_group'),
            notification_type=SystemNotification.TYPE_SYSTEM,
        )
        m.notified_at = timezone.now()
        m.save(update_fields=['notified_at'])
        sent += 1
    return sent


def groups_for_user(user):
    """The user's reading groups with members, for the student pages."""
    ids = ReadingGroupMember.objects.filter(user=user).values_list('group_id', flat=True)
    return list(
        ReadingGroup.objects.filter(pk__in=ids)
        .select_related('course').prefetch_related('members__user').order_by('course__code', 'number')
    )
