from datetime import date, datetime

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from attendance.models import ClassSession, Course


class Command(BaseCommand):
    help = ("Change the start and end time of a course's class sessions, e.g. "
            "set_course_time 'KISW 105B' 11:30 13:20. Only sessions dated today or later "
            "are changed unless --all is given. DRY RUN with --dry-run.")

    def add_arguments(self, parser):
        parser.add_argument('code', help="Course code, e.g. 'KISW 105B'")
        parser.add_argument('start', help='New start time HH:MM (24h)')
        parser.add_argument('end', help='New end time HH:MM (24h)')
        parser.add_argument('--all', action='store_true', help='Also change sessions in the past')
        parser.add_argument('--dry-run', action='store_true')

    @transaction.atomic
    def handle(self, *args, **o):
        try:
            start = datetime.strptime(o['start'], '%H:%M').time()
            end = datetime.strptime(o['end'], '%H:%M').time()
        except ValueError:
            raise CommandError('Times must look like 11:30 (24-hour HH:MM).')
        if end <= start:
            raise CommandError('End time must be after the start time.')
        course = Course.objects.filter(code=o['code']).first()
        if not course:
            raise CommandError(f"No course with code {o['code']!r}.")

        sessions = ClassSession.objects.filter(course=course)
        if not o['all']:
            sessions = sessions.filter(date__gte=date.today())
        # One row at a time so a changed start can never collide with an existing
        # session, and so each change is reported.
        changed = 0
        for s in sessions.order_by('date'):
            if s.start_time == start and s.end_time == end:
                continue
            if ClassSession.objects.filter(course=course, date=s.date, start_time=start).exclude(pk=s.pk).exists():
                self.stdout.write(self.style.WARNING(f'  skipped {s.date}: a session at {start:%H:%M} already exists'))
                continue
            self.stdout.write(f'  {s.date}: {s.start_time:%H:%M}-{s.end_time:%H:%M} -> {start:%H:%M}-{end:%H:%M}')
            s.start_time, s.end_time = start, end
            s.save(update_fields=['start_time', 'end_time'])
            changed += 1
        self.stdout.write(self.style.SUCCESS(f'{course.code}: {changed} session(s) updated.'))
        if o['dry_run']:
            transaction.set_rollback(True)
            self.stdout.write(self.style.WARNING('DRY RUN - nothing saved.'))
