from datetime import date

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from attendance.models import (
    AttendanceRecord, Course, CourseRegistration, ClassSession, Level, Semester,
)

# First-semester 2026/27 timetable (KISW 1ST SEM TIMETABLE 26-27).
# (code, title, level). KISW 105 has two groups (Mon / Thu) but stays one course.
TIMETABLE = [
    ('KISW 105A', 'Introduction to Kiswahili Studies I (Monday Group)', '100'),
    ('KISW 105B', 'Introduction to Kiswahili Studies I (Thursday Group)', '100'),
    ('KISW 103', 'Elementary Kiswahili Grammar I', '100'),
    ('KISW 201', 'Kiswahili Grammar and Translation I', '200'),
    ('KISW 203', 'Oral and Composition I', '200'),
    ('KISW 205', 'Swahili History and Civilization', '200'),
    ('KISW 301', 'Intermediate Kiswahili Usage I', '300'),
    ('KISW 303', 'Comprehension and Oral Expression I', '300'),
    ('KISW 305', 'Translation Skills', '300'),
    ('KISW 315', 'Figures of Speech and Comprehension', '300'),
    ('KISW 401', 'Advanced Kiswahili Proficiency I', '400'),
    ('KISW 403', 'Oral for Academic and Advanced Purposes', '400'),
    ('KISW 413', 'Modern Kiswahili Drama', '400'),
    ('KISW 415', 'Essay Writing and Comprehension', '400'),
]
# Old code -> new code, so renamed courses keep their row instead of being dropped.
RENAMED = {'KISW 309': 'KISW 315', 'KISW 105': 'KISW 105A'}


class Command(BaseCommand):
    help = "Make the first semester active (second inactive) and replace its courses with the new timetable."

    def add_arguments(self, parser):
        parser.add_argument('--start', help='Semester start date YYYY-MM-DD (optional)')
        parser.add_argument('--end', help='Semester end date YYYY-MM-DD (optional)')
        parser.add_argument('--clear-old-sessions', action='store_true',
                            help='Delete last year\'s sessions on these courses (never those with attendance records)')
        parser.add_argument('--dry-run', action='store_true')

    @transaction.atomic
    def handle(self, *args, **o):
        first = Semester.objects.filter(name__icontains='first').order_by('-year', '-id').first()
        if not first:
            raise CommandError('No First Semester found.')
        self.stdout.write(f'First semester: id={first.id} {first.name} {first.year}')

        if o['start']:
            first.start_date = date.fromisoformat(o['start'])
        if o['end']:
            first.end_date = date.fromisoformat(o['end'])
        first.is_active, first.is_archived = True, False
        first.save()
        n = Semester.objects.exclude(pk=first.pk).filter(is_active=True).update(is_active=False)
        self.stdout.write(f'Activated first semester; deactivated {n} other semester(s).')

        keep = set()
        for code, title, lvl in TIMETABLE:
            level = Level.objects.get(name=lvl)
            old = next((k for k, v in RENAMED.items() if v == code), None)
            course = (Course.objects.filter(code=code).first()
                      or (Course.objects.filter(code=old).first() if old else None))
            if course:
                course.code, course.name, course.level, course.semester = code, title, level, first
                course.save()
                self.stdout.write(f'  updated {code}')
            else:
                course = Course.objects.create(code=code, name=title, level=level, semester=first)
                self.stdout.write(f'  created {code}')
            keep.add(course.pk)

        for c in Course.objects.filter(semester=first).exclude(pk__in=keep):
            used = (CourseRegistration.objects.filter(course=c).exists()
                    or AttendanceRecord.objects.filter(class_session__course=c).exists())
            if used:
                self.stdout.write(self.style.WARNING(f'  KEPT {c.code} (not in timetable but has registrations/attendance) - review in admin'))
            else:
                c.delete()
                self.stdout.write(f'  removed {c.code} (not in timetable, no data)')

        if o['clear_old_sessions']:
            qs = ClassSession.objects.filter(course__in=keep).exclude(attendancerecord__isnull=False)
            self.stdout.write(f'  deleted {qs.count()} old session(s) with no attendance')
            qs.delete()

        if o['dry_run']:
            transaction.set_rollback(True)
            self.stdout.write(self.style.WARNING('DRY RUN - rolled back'))
