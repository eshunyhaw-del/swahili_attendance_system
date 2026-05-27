from django.db import migrations
from datetime import timedelta


def load_courses_and_sessions(apps, schema_editor):
    Level = apps.get_model('attendance', 'Level')
    Semester = apps.get_model('attendance', 'Semester')
    Course = apps.get_model('attendance', 'Course')
    ClassSession = apps.get_model('attendance', 'ClassSession')
    User = apps.get_model('auth', 'User')

    # Get or create levels
    level_100, _ = Level.objects.get_or_create(name='100')
    level_200, _ = Level.objects.get_or_create(name='200')
    level_300, _ = Level.objects.get_or_create(name='300')
    level_400, _ = Level.objects.get_or_create(name='400')

    # Get or create semesters
    sem1, _ = Semester.objects.get_or_create(
        name='First Semester', year=2026,
        defaults={'start_date': '2026-01-01', 'end_date': '2026-06-30', 'is_active': True}
    )
    sem2, _ = Semester.objects.get_or_create(
        name='Second Semester', year=2026,
        defaults={'start_date': '2026-08-01', 'end_date': '2026-12-31', 'is_active': False}
    )

    # Get admin user for lecturer (or create placeholder)
    lecturer = User.objects.filter(is_staff=True).first()

    def add_course(code, title, level, semester):
        course, _ = Course.objects.get_or_create(
            code=code,
            defaults={
                'name': title,
                'level': level,
                'semester': semester,
            }
        )
        return course

    def create_weekly_sessions(course, start_date, weeks=12):
        if not lecturer:
            return
        for i in range(weeks):
            session_date = start_date + timedelta(weeks=i)
            ClassSession.objects.get_or_create(
                course=course,
                date=session_date,
                defaults={
                    'topic': f'Week {i+1}: {course.name}',
                    'lecturer': lecturer
                }
            )

    # ==================== LEVEL 100 ====================
    # First Semester
    c = add_course('KISW 101', 'Introduction to Kiswahili Studies', level_100, sem1)
    create_weekly_sessions(c, sem1.start_date)

    c = add_course('KISW 103', 'Elementary Kiswahili Grammar I', level_100, sem1)
    create_weekly_sessions(c, sem1.start_date)

    # Second Semester
    c = add_course('KISW 102', 'Oral Communication Skills', level_100, sem2)
    create_weekly_sessions(c, sem2.start_date)

    c = add_course('KISW 104', 'Elementary Kiswahili Grammar II', level_100, sem2)
    create_weekly_sessions(c, sem2.start_date)

    # ==================== LEVEL 200 ====================
    # First Semester
    c = add_course('KISW 201', 'Kiswahili Grammar and Translation I', level_200, sem1)
    create_weekly_sessions(c, sem1.start_date)

    c = add_course('KISW 203', 'Oral and Composition I', level_200, sem1)
    create_weekly_sessions(c, sem1.start_date)

    c = add_course('KISW 205', 'Swahili History and Civilization', level_200, sem1)
    create_weekly_sessions(c, sem1.start_date)

    # Second Semester
    c = add_course('KISW 202', 'Kiswahili Grammar and Translation II', level_200, sem2)
    create_weekly_sessions(c, sem2.start_date)

    c = add_course('KISW 204', 'Oral and Composition II', level_200, sem2)
    create_weekly_sessions(c, sem2.start_date)

    c = add_course('KISW 206', 'Introduction to Kiswahili Literature', level_200, sem2)
    create_weekly_sessions(c, sem2.start_date)

    # ==================== LEVEL 300 ====================
    # First Semester - Core
    c = add_course('KISW 301', 'Intermediate Kiswahili Usage I', level_300, sem1)
    create_weekly_sessions(c, sem1.start_date)

    c = add_course('KISW 303', 'Comprehension and Oral Expression I', level_300, sem1)
    create_weekly_sessions(c, sem1.start_date)

    # First Semester - Electives
    c = add_course('KISW 305', 'Language and Translation Skills', level_300, sem1)
    create_weekly_sessions(c, sem1.start_date)

    c = add_course('KISW 307', 'Special Topics I', level_300, sem1)
    create_weekly_sessions(c, sem1.start_date)

    c = add_course('KISW 309', 'Kiswahili Literature of the 17th-20th Century', level_300, sem1)
    create_weekly_sessions(c, sem1.start_date)

    c = add_course('KISW 310', 'Language Immersion I', level_300, sem1)
    create_weekly_sessions(c, sem1.start_date)

    c = add_course('KISW 311', 'Study of Kiswahili Songs', level_300, sem1)
    create_weekly_sessions(c, sem1.start_date)

    c = add_course('KISW 313', 'Study of Kiswahili Poetic Structures', level_300, sem1)
    create_weekly_sessions(c, sem1.start_date)

    c = add_course('KISW 315', 'Figures of Speech and Comprehension', level_300, sem1)
    create_weekly_sessions(c, sem1.start_date)

    c = add_course('KISW 317', 'Contemporary Politics in East Africa', level_300, sem1)
    create_weekly_sessions(c, sem1.start_date)

    c = add_course('KISW 319', 'The Swahili Media', level_300, sem1)
    create_weekly_sessions(c, sem1.start_date)

    # Second Semester - Core
    c = add_course('KISW 302', 'Intermediate Kiswahili Usage II', level_300, sem2)
    create_weekly_sessions(c, sem2.start_date)

    c = add_course('KISW 304', 'Comprehension and Oral Expression II', level_300, sem2)
    create_weekly_sessions(c, sem2.start_date)

    # Second Semester - Electives
    c = add_course('KISW 306', 'Translation Exercises', level_300, sem2)
    create_weekly_sessions(c, sem2.start_date)

    c = add_course('KISW 308', 'Special Topics II', level_300, sem2)
    create_weekly_sessions(c, sem2.start_date)

    c = add_course('KISW 312', 'Kiswahili Oral Literature', level_300, sem2)
    create_weekly_sessions(c, sem2.start_date)

    c = add_course('KISW 314', 'Figures of Speech and Comprehension', level_300, sem2)
    create_weekly_sessions(c, sem2.start_date)

    c = add_course('KISW 316', 'Globalization and the Swahili Society', level_300, sem2)
    create_weekly_sessions(c, sem2.start_date)

    c = add_course('KISW 318', 'Cinema in Swahili Society', level_300, sem2)
    create_weekly_sessions(c, sem2.start_date)

    # ==================== LEVEL 400 ====================
    # First Semester - Core
    c = add_course('KISW 401', 'Advanced Kiswahili Proficiency I', level_400, sem1)
    create_weekly_sessions(c, sem1.start_date)

    c = add_course('KISW 403', 'Oral for Academic and Professional Purposes', level_400, sem1)
    create_weekly_sessions(c, sem1.start_date)

    # First Semester - Electives
    c = add_course('KISW 400', 'Long Essay', level_400, sem1)
    create_weekly_sessions(c, sem1.start_date)

    c = add_course('DMLA 401', 'Research Methods', level_400, sem1)
    create_weekly_sessions(c, sem1.start_date)

    c = add_course('KISW 405', 'Advanced Translation Skills I', level_400, sem1)
    create_weekly_sessions(c, sem1.start_date)

    c = add_course('KISW 407', 'Selected Topics I', level_400, sem1)
    create_weekly_sessions(c, sem1.start_date)

    c = add_course('KISW 409', 'Gender in Kiswahili Literary Writings', level_400, sem1)
    create_weekly_sessions(c, sem1.start_date)

    c = add_course('KISW 410', 'Language Immersion II', level_400, sem1)
    create_weekly_sessions(c, sem1.start_date)

    c = add_course('KISW 411', 'History of Kiswahili Language Institutions', level_400, sem1)
    create_weekly_sessions(c, sem1.start_date)

    c = add_course('KISW 413', 'Modern Kiswahili Drama', level_400, sem1)
    create_weekly_sessions(c, sem1.start_date)

    c = add_course('KISW 415', 'Essay Writing and Comprehension', level_400, sem1)
    create_weekly_sessions(c, sem1.start_date)

    c = add_course('KISW 417', 'Tourism in Swahili Society', level_400, sem1)
    create_weekly_sessions(c, sem1.start_date)

    c = add_course('KISW 419', 'Popular Culture in Swahili Society', level_400, sem1)
    create_weekly_sessions(c, sem1.start_date)

    # Second Semester - Core
    c = add_course('KISW 402', 'Advanced Kiswahili Proficiency II', level_400, sem2)
    create_weekly_sessions(c, sem2.start_date)

    c = add_course('KISW 404', 'Advanced Oral Expression', level_400, sem2)
    create_weekly_sessions(c, sem2.start_date)

    # Second Semester - Electives
    c = add_course('KISW 406', 'Advanced Translation Skills II', level_400, sem2)
    create_weekly_sessions(c, sem2.start_date)

    c = add_course('KISW 408', 'Selected Topics II', level_400, sem2)
    create_weekly_sessions(c, sem2.start_date)

    c = add_course('KISW 412', 'Kiswahili Poetry of the 17th - 20th Century', level_400, sem2)
    create_weekly_sessions(c, sem2.start_date)

    c = add_course('KISW 414', 'Contemporary Kiswahili Literature', level_400, sem2)
    create_weekly_sessions(c, sem2.start_date)

    c = add_course('KISW 416', 'Nationalism and Identity of the Swahili People', level_400, sem2)
    create_weekly_sessions(c, sem2.start_date)

    c = add_course('KISW 418', 'Kiswahili in the Diaspora', level_400, sem2)
    create_weekly_sessions(c, sem2.start_date)

    c = add_course('KISW 420', 'Study Abroad', level_400, sem2)
    create_weekly_sessions(c, sem2.start_date)

    c = add_course('KISW 422', 'Teaching of Kiswahili as a Foreign Language', level_400, sem2)
    create_weekly_sessions(c, sem2.start_date)


def delete_all(apps, schema_editor):
    Course = apps.get_model('attendance', 'Course')
    ClassSession = apps.get_model('attendance', 'ClassSession')
    ClassSession.objects.all().delete()
    Course.objects.filter(code__startswith='KISW').delete()
    Course.objects.filter(code='DMLA 401').delete()


class Migration(migrations.Migration):

    dependencies = [
        ('attendance', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(load_courses_and_sessions, delete_all),
    ]