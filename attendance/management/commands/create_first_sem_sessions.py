from datetime import date, datetime, timedelta

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from attendance.models import ClassSession, Course, Level, Semester

# code, title, level, weekday (Mon=0), start, end, venue - from the 2026/27 first-semester timetable.
# KISW 105 has two groups on different days, so it is split into two courses (like 106A/106B).
SLOTS = [
    ('KISW 105A', 'Introduction to Kiswahili Studies I (Monday Group)', '100', 0, '15:30', '17:20', 'GCB Main'),
    ('KISW 105B', 'Introduction to Kiswahili Studies I (Thursday Group)', '100', 3, '11:30', '13:20', 'SOE SF1'),
    ('KISW 103', 'Elementary Kiswahili Grammar I', '100', 2, '11:30', '13:30', 'KAB'),
    ('KISW 201', 'Kiswahili Grammar and Translation I', '200', 3, '07:30', '09:20', 'JQB 12'),
    ('KISW 203', 'Oral and Composition I', '200', 0, '13:30', '15:20', 'LLT'),
    ('KISW 205', 'Swahili History and Civilization', '200', 3, '13:30', '15:20', 'JQB 11'),
    ('KISW 301', 'Intermediate Kiswahili Usage I', '300', 3, '11:30', '13:20', 'JQB 12'),
    ('KISW 303', 'Comprehension and Oral Expression I', '300', 1, '13:30', '15:20', 'E 10'),
    ('KISW 305', 'Translation Skills', '300', 4, '09:30', '11:20', 'LLT'),
    ('KISW 315', 'Figures of Speech and Comprehension', '300', 4, '13:30', '15:20', 'E 10'),
    ('KISW 401', 'Advanced Kiswahili Proficiency I', '400', 2, '09:30', '11:30', 'E 10'),
    ('KISW 403', 'Oral for Academic and Advanced Purposes', '400', 3, '13:30', '15:20', 'E 10'),
    ('KISW 413', 'Modern Kiswahili Drama', '400', 0, '15:30', '17:20', 'E 10'),
    ('KISW 415', 'Essay Writing and Comprehension', '400', 1, '15:30', '17:20', 'K. Folson'),
]


class Command(BaseCommand):
    help = ("Create the weekly class sessions for the first semester from the timetable. "
            "Safe to re-run: existing sessions are skipped. DRY RUN with --dry-run.")

    def add_arguments(self, parser):
        parser.add_argument('--start', default='2026-10-26', help='Week 1 Monday (YYYY-MM-DD)')
        parser.add_argument('--weeks', type=int, default=13)
        parser.add_argument('--lecturer', help='Username for the lecturer field (default: first superuser)')
        parser.add_argument('--dry-run', action='store_true')

    @transaction.atomic
    def handle(self, *args, **o):
        monday = date.fromisoformat(o['start'])
        if monday.weekday() != 0:
            raise CommandError(f'{monday} is not a Monday.')
        sem = Semester.objects.filter(is_active=True, is_archived=False).first()
        if not sem:
            raise CommandError('No active semester.')
        lect = (User.objects.filter(username=o['lecturer']).first() if o['lecturer']
                else User.objects.filter(is_superuser=True).order_by('id').first())
        if not lect:
            raise CommandError('No lecturer user found; pass --lecturer USERNAME.')
        self.stdout.write(f'Semester: {sem.name} {sem.year}; lecturer: {lect.username}; week 1 = {monday}')

        # KISW 105 becomes the Monday group; add the Thursday group beside it.
        old = Course.objects.filter(code='KISW 105').first()
        if old and not Course.objects.filter(code='KISW 105A').exists():
            old.code, old.name = 'KISW 105A', SLOTS[0][1]
            old.save()
            self.stdout.write('  renamed KISW 105 -> KISW 105A')

        created = skipped = 0
        for code, name, lvl, wd, start, end, venue in SLOTS:
            course, made = Course.objects.get_or_create(
                code=code, defaults={'name': name, 'level': Level.objects.get(name=lvl), 'semester': sem})
            if not made and (course.semester_id != sem.id or course.name != name):
                course.name, course.semester = name, sem
                course.save()
            if made:
                self.stdout.write(f'  created course {code}')
            st = datetime.strptime(start, '%H:%M').time()
            en = datetime.strptime(end, '%H:%M').time()
            n = 0
            for wk in range(o['weeks']):
                day = monday + timedelta(weeks=wk, days=wd)
                _, new = ClassSession.objects.get_or_create(
                    course=course, date=day, start_time=st,
                    defaults={'end_time': en, 'topic': venue, 'lecturer': lect})
                created += new
                skipped += (not new)
                n += new
            self.stdout.write(f'  {code}: {n} new session(s), first {monday + timedelta(days=wd)}')
        self.stdout.write(self.style.SUCCESS(f'Created {created}, skipped {skipped} existing.'))
        if o['dry_run']:
            transaction.set_rollback(True)
            self.stdout.write(self.style.WARNING('DRY RUN - nothing saved.'))
