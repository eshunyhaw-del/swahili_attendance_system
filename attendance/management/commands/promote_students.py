from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from attendance.models import (
    AttendanceRecord, Course, CourseRegistration, Level, TAProfile, UserProfile,
)

NEXT = [('400', None), ('300', '400'), ('200', '300'), ('100', '200')]  # order matters


class Command(BaseCommand):
    help = (
        "Academic-year rollover: 100->200, 200->300, 300->400, last year's 400 become graduates, "
        "last year's course registrations are deactivated, and old TAs are retired to the alumni page. "
        "DRY RUN unless --yes is given. Run ONCE per year, after a database backup."
    )

    def add_arguments(self, parser):
        parser.add_argument('--yes', action='store_true', help='Actually apply the changes.')
        parser.add_argument('--keep-ta', action='append', default=[], metavar='EMAIL',
                            help='TA email to keep active (repeatable).')

    @transaction.atomic
    def handle(self, *args, **o):
        dry = not o['yes']
        levels = {l.name: l for l in Level.objects.all()}
        if not all(n in levels for n in ('100', '200', '300', '400')):
            raise CommandError('Levels 100-400 must exist.')
        if UserProfile.objects.filter(is_graduate=False, level__isnull=True).exists():
            self.stdout.write(self.style.WARNING('Note: some active students have no level; they are left untouched.'))

        # 1. Move levels, highest first so nobody is promoted twice.
        for cur, nxt in NEXT:
            qs = UserProfile.objects.filter(level=levels[cur], is_graduate=False, user__is_staff=False)
            n = qs.count()
            if nxt is None:
                qs.update(is_graduate=True, level=None)
                self.stdout.write(f'Level 400 -> graduates: {n}')
            else:
                qs.update(level=levels[nxt])
                self.stdout.write(f'Level {cur} -> {nxt}: {n}')

        # 2. Deactivate last year's registrations (kept as history, nothing deleted).
        regs = CourseRegistration.objects.filter(is_active=True)
        self.stdout.write(f'Deactivated course registrations: {regs.count()}')
        regs.update(is_active=False, deregistered_at=timezone.now())

        # 3. Retire old TAs (they only see the alumni invite); new TAs register and are approved afresh.
        keep = {e.lower() for e in o['keep_ta']}
        retired = []
        for ta in TAProfile.objects.select_related('user'):
            if (ta.user.email or '').lower() in keep:
                continue
            # Retired: unapproved + inactive. They can still log in, but are sent only to
            # the alumni invite page (middleware) and cannot use any TA feature.
            ta.is_active = False
            ta.is_approved = False
            ta.save(update_fields=['is_active', 'is_approved'])
            retired.append(ta.user.email or ta.user.username)
        self.stdout.write(f'Retired TAs ({len(retired)}): ' + ', '.join(retired))

        # 4. Warn about old attendance still attached to reused active-semester courses.
        leftover = AttendanceRecord.objects.filter(class_session__course__semester__is_active=True).count()
        if leftover:
            self.stdout.write(self.style.WARNING(
                f'{leftover} attendance record(s) from an earlier year are attached to active-semester courses '
                'and will count toward this semester. Review in admin.'))

        if dry:
            transaction.set_rollback(True)
            self.stdout.write(self.style.WARNING('DRY RUN - nothing changed. Re-run with --yes to apply.'))
        else:
            self.stdout.write(self.style.SUCCESS('Rollover applied.'))
