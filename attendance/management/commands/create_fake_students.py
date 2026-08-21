"""Create (or delete) fake students for testing.

Usage:
    python manage.py create_fake_students                # 50 per level = 200
    python manage.py create_fake_students --per-level 25  # 25 per level = 100
    python manage.py create_fake_students --no-register   # don't enrol them
    python manage.py create_fake_students --delete        # remove all fakes

Fake accounts are identified by the username prefix ``fake_`` and student IDs
starting with ``FS`` so they can be cleaned up without touching real students.
All fakes share the password ``Test@2026``.
"""

import random

from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from django.db import transaction

from attendance.models import (
    Level, Semester, Course, UserProfile, CourseRegistration,
)

USERNAME_PREFIX = "fake_"
STUDENT_ID_PREFIX = "FS"
PASSWORD = "Test@2026"

FIRST_NAMES = [
    "Kwame", "Ama", "Kofi", "Akosua", "Yaw", "Abena", "Kwabena", "Adwoa",
    "Kojo", "Efua", "Kwaku", "Esi", "Fiifi", "Araba", "Kwesi", "Aba",
    "Nana", "Maame", "Kojo", "Afia", "Zainab", "Musa", "Amina", "Ibrahim",
    "Fatima", "Yusuf", "Halima", "Salim", "Rehema", "Juma", "Neema", "Baraka",
]
LAST_NAMES = [
    "Mensah", "Owusu", "Boateng", "Asante", "Agyeman", "Darko", "Appiah",
    "Osei", "Adjei", "Frimpong", "Antwi", "Bediako", "Yeboah", "Danso",
    "Acheampong", "Ofori", "Sarpong", "Amoah", "Gyasi", "Nkrumah",
    "Abdallah", "Mohammed", "Ali", "Ismail", "Rahman",
]


class Command(BaseCommand):
    help = "Create or delete fake students across all levels for testing."

    def add_arguments(self, parser):
        parser.add_argument('--per-level', type=int, default=50,
                            help='How many students to create per level (default 50).')
        parser.add_argument('--no-register', action='store_true',
                            help="Don't enrol the students in their level's active courses.")
        parser.add_argument('--delete', action='store_true',
                            help='Delete all fake students instead of creating them.')

    def handle(self, *args, **opts):
        if opts['delete']:
            return self._delete()

        per_level = opts['per_level']
        do_register = not opts['no_register']

        levels = list(Level.objects.all().order_by('name'))
        if not levels:
            self.stderr.write("No levels exist. Seed levels first.")
            return

        semester = (
            Semester.objects.filter(is_active=True, is_archived=False).first()
            or Semester.objects.filter(is_archived=False).first()
        )

        created = 0
        # Continue numbering after any existing fakes so re-runs don't collide.
        existing = UserProfile.objects.filter(
            student_id_number__startswith=STUDENT_ID_PREFIX
        ).count()
        counter = existing + 1

        for level in levels:
            courses = []
            if do_register and semester:
                courses = list(Course.objects.filter(level=level, semester=semester))
                # Level 100 has two KISW 106 groups; a student may only be in one.
                if any(c.code == 'KISW 106A' for c in courses):
                    courses = [c for c in courses if c.code != 'KISW 106B']

            for _ in range(per_level):
                sid = f"{STUDENT_ID_PREFIX}{level.name}{counter:04d}"
                username = f"{USERNAME_PREFIX}{level.name}_{counter:04d}"
                counter += 1
                first = random.choice(FIRST_NAMES)
                last = random.choice(LAST_NAMES)

                with transaction.atomic():
                    user = User.objects.create(
                        username=username,
                        email=f"{username}@example.com",
                        first_name=first,
                        last_name=last,
                        is_active=True,
                    )
                    user.set_password(PASSWORD)
                    user.save()

                    profile = UserProfile.objects.create(
                        user=user,
                        level=level,
                        student_id_number=sid,
                        student_email=user.email,
                        email_verified=True,
                        must_change_password=False,
                    )

                    for course in courses:
                        CourseRegistration.objects.get_or_create(
                            user_profile=profile, course=course,
                            defaults={'is_active': True},
                        )
                created += 1

            self.stdout.write(f"  Level {level.name}: +{per_level} students"
                              + (f" enrolled in {len(courses)} course(s)" if do_register else ""))

        self.stdout.write(self.style.SUCCESS(
            f"Created {created} fake students. Login password for all: {PASSWORD}"
        ))
        self.stdout.write("Delete them later with: python manage.py create_fake_students --delete")

    def _delete(self):
        users = User.objects.filter(username__startswith=USERNAME_PREFIX)
        n = users.count()
        users.delete()  # cascades to UserProfile + CourseRegistration
        self.stdout.write(self.style.SUCCESS(f"Deleted {n} fake students."))
