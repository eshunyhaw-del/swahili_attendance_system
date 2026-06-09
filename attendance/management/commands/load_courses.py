from django.core.management.base import BaseCommand
from datetime import date, timedelta
from django.contrib.auth.models import User
from django.db import transaction

from attendance.models import (
    Course, Level, Semester, ClassSession,
    UserProfile, TAProfile,
)


FIRST_SEM_START  = date(2025, 9, 1)    # Week 1 = Mon 1 Sep 2025
SECOND_SEM_START = date(2026, 1, 19)   # Week 1 = Mon 19 Jan 2026
WEEKS_PER_SEM    = 13

# start_time / end_time by level name
LEVEL_TIMES = {
    '100': ('07:30', '09:20'),
    '200': ('09:30', '11:20'),
    '300': ('11:30', '13:20'),
    '400': ('13:30', '15:20'),
}

COURSES = [
    # ── FIRST SEMESTER ────────────────────────────────────────────────────────
    # Level 100
    {'code': 'KISW 105', 'name': 'Introduction to Kiswahili Studies',          'level': '100', 'sem': 1},
    {'code': 'KISW 103', 'name': 'Elementary Kiswahili Grammar I',              'level': '100', 'sem': 1},
    # Level 200
    {'code': 'KISW 201', 'name': 'Kiswahili Grammar and Translation I',         'level': '200', 'sem': 1},
    {'code': 'KISW 203', 'name': 'Comprehension and Oral Expression I',         'level': '200', 'sem': 1},
    {'code': 'KISW 205', 'name': 'Swahili History and Civilization',            'level': '200', 'sem': 1},
    # Level 300
    {'code': 'KISW 301', 'name': 'Intermediate Kiswahili Usage I',              'level': '300', 'sem': 1},
    {'code': 'KISW 303', 'name': 'Comprehension and Oral Expression I',         'level': '300', 'sem': 1},
    {'code': 'KISW 305', 'name': 'Language and Translation Skills',             'level': '300', 'sem': 1},
    {'code': 'KISW 309', 'name': 'Figures of Speech and Comprehension',         'level': '300', 'sem': 1},
    # Level 400
    {'code': 'KISW 401', 'name': 'Advanced Kiswahili Proficiency I',            'level': '400', 'sem': 1},
    {'code': 'KISW 403', 'name': 'Oral for Academic and Professional Purposes', 'level': '400', 'sem': 1},
    {'code': 'KISW 413', 'name': 'Modern Kiswahili Drama',                      'level': '400', 'sem': 1},
    {'code': 'KISW 415', 'name': 'Essay Writing and Comprehension',             'level': '400', 'sem': 1},
    {'code': 'KISW 420', 'name': 'Study Abroad',                                'level': '400', 'sem': 1},

    # ── SECOND SEMESTER ───────────────────────────────────────────────────────
    # Level 100
    {'code': 'KISW 106', 'name': 'Introduction to Kiswahili Studies II',        'level': '100', 'sem': 2},
    {'code': 'KISW 104', 'name': 'Elementary Kiswahili Grammar II',             'level': '100', 'sem': 2},
    # Level 200
    {'code': 'KISW 202', 'name': 'Kiswahili Grammar and Translation II',        'level': '200', 'sem': 2},
    {'code': 'KISW 204', 'name': 'Oral and Composition II',                     'level': '200', 'sem': 2},
    {'code': 'KISW 206', 'name': 'Introduction to Kiswahili Literature',        'level': '200', 'sem': 2},
    # Level 300
    {'code': 'KISW 302', 'name': 'Intermediate Kiswahili Usage II',             'level': '300', 'sem': 2},
    {'code': 'KISW 304', 'name': 'Comprehension and Oral Expression II',        'level': '300', 'sem': 2},
    {'code': 'KISW 306', 'name': 'Translation Exercises',                       'level': '300', 'sem': 2},
    {'code': 'KISW 312', 'name': 'Kiswahili Oral Literature',                   'level': '300', 'sem': 2},
    # Level 400
    {'code': 'KISW 402', 'name': 'Advanced Kiswahili Proficiency II',           'level': '400', 'sem': 2},
    {'code': 'KISW 404', 'name': 'Advanced Oral Expression',                    'level': '400', 'sem': 2},
    {'code': 'KISW 406', 'name': 'Advanced Kiswahili Translation II',           'level': '400', 'sem': 2},
    {'code': 'KISW 414', 'name': 'Contemporary Kiswahili Literature',           'level': '400', 'sem': 2},
    # KISW 420 code is already used by Sem 1; Study Abroad is a year-long
    # enrolment — stored under the Sem 1 course for both halves.
]


class Command(BaseCommand):
    help = 'Reset all course data to the official SWASA 2025/2026 distribution'

    @transaction.atomic
    def handle(self, *args, **kwargs):
        w = self.stdout.write
        ok  = self.style.SUCCESS
        err = self.style.ERROR
        hdr = self.style.HTTP_INFO

        # ── 0. Find lecturer ──────────────────────────────────────────────────
        lecturer = User.objects.filter(is_staff=True).order_by('id').first()
        if not lecturer:
            w(err('No staff user found — create one first.'))
            return
        w(hdr(f'\nLecturer: {lecturer.username} (id={lecturer.id})'))

        # ── 1. Clear M2M course registrations (students) ─────────────────────
        w(hdr('\n[1/6] Clearing student course registrations...'))
        for profile in UserProfile.objects.prefetch_related('registered_courses'):
            count = profile.registered_courses.count()
            if count:
                profile.registered_courses.clear()
                w(f'     Cleared {count} course(s) for {profile.user.username}')

        # Also clear TA assigned_courses
        for ta in TAProfile.objects.prefetch_related('assigned_courses'):
            if ta.assigned_courses.exists():
                ta.assigned_courses.clear()
                w(f'     Cleared assigned_courses for TA {ta.user.username}')

        # ── 2. Delete class sessions then courses ─────────────────────────────
        w(hdr('\n[2/6] Deleting existing class sessions...'))
        s_del = ClassSession.objects.all().delete()
        w(f'     Deleted {s_del[0]} session(s)')

        w(hdr('\n[3/6] Deleting existing courses...'))
        c_del = Course.objects.all().delete()
        w(f'     Deleted {c_del[0]} course(s)')

        # ── 3. Wipe and recreate semesters ────────────────────────────────────
        w(hdr('\n[4/6] Resetting semesters...'))
        Semester.objects.all().delete()

        sem1 = Semester.objects.create(
            name='First Semester 2025/2026',
            year=2025,
            start_date=date(2025, 9, 1),
            end_date=date(2025, 12, 12),
            is_active=True,
            is_archived=False,
        )
        sem2 = Semester.objects.create(
            name='Second Semester 2025/2026',
            year=2026,
            start_date=date(2026, 1, 19),
            end_date=date(2026, 5, 9),
            is_active=False,
            is_archived=False,
        )
        w(f'     + {sem1}')
        w(f'     + {sem2}')

        # ── 4. Ensure levels exist ────────────────────────────────────────────
        w(hdr('\n[5/6] Ensuring levels exist...'))
        levels = {}
        for name in ('100', '200', '300', '400'):
            obj, created = Level.objects.get_or_create(name=name)
            levels[name] = obj
            w(f'     {"+" if created else "="} Level {name}')

        sem_map = {1: sem1, 2: sem2}
        sem_start = {1: FIRST_SEM_START, 2: SECOND_SEM_START}

        # ── 5. Create courses and sessions ────────────────────────────────────
        w(hdr('\n[6/6] Creating courses and class sessions...'))
        course_count = 0
        session_count = 0

        for cd in COURSES:
            course = Course.objects.create(
                code=cd['code'],
                name=cd['name'],
                level=levels[cd['level']],
                semester=sem_map[cd['sem']],
            )
            course_count += 1

            start, end = LEVEL_TIMES[cd['level']]
            base = sem_start[cd['sem']]

            sessions = [
                ClassSession(
                    course=course,
                    date=base + timedelta(weeks=i),
                    start_time=start,
                    end_time=end,
                    topic=f'Week {i + 1}',
                    lecturer=lecturer,
                )
                for i in range(WEEKS_PER_SEM)
            ]
            ClassSession.objects.bulk_create(sessions)
            session_count += WEEKS_PER_SEM

            w(f'     [{cd["sem"]}] {course.code} | {course.name} | L{cd["level"]} — {WEEKS_PER_SEM} sessions')

        # ── Summary ───────────────────────────────────────────────────────────
        w(ok(
            f'\n{"="*60}\n'
            f'  DONE\n'
            f'  Semesters : 2\n'
            f'  Levels    : 4\n'
            f'  Courses   : {course_count}\n'
            f'  Sessions  : {session_count} ({WEEKS_PER_SEM} per course)\n'
            f'  Note      : KISW 420 (Study Abroad) is stored under\n'
            f'              First Semester only (unique code constraint).\n'
            f'{"="*60}'
        ))
