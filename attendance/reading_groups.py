"""Reading groups: load a lecturer's group list and link names to student accounts."""

import re
from difflib import SequenceMatcher

from django.contrib.auth.models import User
from django.db.models import Q
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


def _candidates(course):
    """Students a listed name may belong to: registrants of the course plus every
    current (non-graduate) student at the course's level. Lecturers' lists often
    include students who have not registered for the course in the app yet."""
    registered = Q(
        userprofile__course_registrations__course=course,
        userprofile__course_registrations__is_active=True,
    )
    same_level = Q(userprofile__level=course.level, userprofile__is_graduate=False)
    return list(
        User.objects.filter(is_active=True, is_staff=False, userprofile__isnull=False)
        .filter(registered | same_level).distinct()
    )


def load_groups(course, groups):
    """Create or update groups/members from [(number, book, [names])] and link users.

    Re-runnable: a manually fixed link is kept, and unmatched names are tried again
    (more students register over time).
    Returns (report_lines, linked_count, unmatched_count).
    """
    candidates = _candidates(course)
    lines, linked, unmatched = [
        f"{len(candidates)} students to match against "
        f"(registered for {course.code} or at level {course.level.name})"
    ], 0, 0
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


def notify_members(course, user=None):
    """Send each newly linked student one notification (only `user`, if given).
    Returns how many were sent."""
    sent = 0
    pending = ReadingGroupMember.objects.filter(
        group__course=course, user__isnull=False, notified_at__isnull=True)
    if user is not None:
        pending = pending.filter(user=user)
    for m in pending.select_related('group', 'user'):
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


def link_new_registrant(user, course):
    """Called when a student registers for `course`: if they are on a reading-group
    list that is still unlinked, link them and send their notification.

    The name is matched against the whole candidate pool, so a name that fits two
    students is still left alone. Returns how many notifications were sent.
    """
    pending = list(ReadingGroupMember.objects.filter(group__course=course, user__isnull=True))
    if not pending:
        return 0
    pool = _candidates(course)
    for m in pending:
        found, _ = match_user(m.listed_name, pool)
        if found is not None and found.pk == user.pk:
            m.user = user
            m.save(update_fields=['user'])
    return notify_members(course, user=user)

