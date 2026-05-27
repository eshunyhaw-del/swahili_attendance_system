from django.core.management.base import BaseCommand
from datetime import datetime, timedelta
from django.contrib.auth.models import User
from attendance.models import Course, Level, Semester, ClassSession

class Command(BaseCommand):
    help = 'Load all courses from both semesters and generate 12 weeks of sessions'

    def handle(self, *args, **kwargs):
        # Delete all existing courses
        self.stdout.write('Deleting all existing courses...')
        Course.objects.all().delete()
        
        # Get or create Level objects
        level_100, _ = Level.objects.get_or_create(name='100')
        level_200, _ = Level.objects.get_or_create(name='200')
        level_300, _ = Level.objects.get_or_create(name='300')
        level_400, _ = Level.objects.get_or_create(name='400')
        
        level_map = {
            100: level_100,
            200: level_200,
            300: level_300,
            400: level_400
        }
        
        # Get or create Semester objects
        sem1, _ = Semester.objects.get_or_create(
            name='First Semester',
            year=2025,
            defaults={
                'start_date': datetime(2025, 9, 1).date(),
                'end_date': datetime(2026, 1, 31).date(),
                'is_active': True
            }
        )
        
        sem2, _ = Semester.objects.get_or_create(
            name='Second Semester',
            year=2026,
            defaults={
                'start_date': datetime(2026, 2, 1).date(),
                'end_date': datetime(2026, 6, 30).date(),
                'is_active': True
            }
        )
        
        semester_map = {
            1: sem1,
            2: sem2
        }
        
        # Get a lecturer user (use the swasa superuser you created)
        try:
            lecturer = User.objects.get(username='swasa')
            self.stdout.write(f'✓ Using existing lecturer: {lecturer.username}')
        except User.DoesNotExist:
            # Create a default lecturer if swasa doesn't exist
            lecturer = User.objects.create_user(
                username='lecturer_default',
                password='lecturer123',
                first_name='Staff',
                last_name='Lecturer',
                is_staff=True
            )
            self.stdout.write('⚠ Created default lecturer user')
        
        # Define all courses
        courses = [
            # ========== FIRST SEMESTER ==========
            {'code': 'KISW 105', 'name': 'Introduction to Kiswahili Studies I', 'level': 100, 'semester': 1},
            {'code': 'KISW 103', 'name': 'Elementary Kiswahili Grammar I', 'level': 100, 'semester': 1},
            {'code': 'KISW 201', 'name': 'Kiswahili Grammar and Translation I', 'level': 200, 'semester': 1},
            {'code': 'KISW 203', 'name': 'Comprehension and Oral Expression I', 'level': 200, 'semester': 1},
            {'code': 'KISW 205', 'name': 'Swahili History and Civilization', 'level': 200, 'semester': 1},
            {'code': 'KISW 301', 'name': 'Intermediate Kiswahili Usage I', 'level': 300, 'semester': 1},
            {'code': 'KISW 303', 'name': 'Comprehension and Oral Expression I', 'level': 300, 'semester': 1},
            {'code': 'KISW 305', 'name': 'Language and Translation Skills', 'level': 300, 'semester': 1},
            {'code': 'KISW 309', 'name': 'Figures of Speech and Comprehension', 'level': 300, 'semester': 1},
            {'code': 'KISW 401', 'name': 'Advanced Kiswahili Proficiency I', 'level': 400, 'semester': 1},
            {'code': 'KISW 403', 'name': 'Oral for Academic and Professional Purposes', 'level': 400, 'semester': 1},
            {'code': 'KISW 413', 'name': 'Modern Kiswahili Drama', 'level': 400, 'semester': 1},
            {'code': 'KISW 415', 'name': 'Essay Writing and Comprehension', 'level': 400, 'semester': 1},
            {'code': 'SWAH 420', 'name': 'Study Abroad', 'level': 400, 'semester': 1},
            
            # ========== SECOND SEMESTER ==========
            {'code': 'KISW 106', 'name': 'Introduction to Kiswahili Studies II', 'level': 100, 'semester': 2},
            {'code': 'KISW 104', 'name': 'Elementary Kiswahili Grammar II', 'level': 100, 'semester': 2},
            {'code': 'KISW 202', 'name': 'Kiswahili Grammar & Translation II', 'level': 200, 'semester': 2},
            {'code': 'KISW 204', 'name': 'Oral and Composition II', 'level': 200, 'semester': 2},
            {'code': 'KISW 206', 'name': 'Introduction to Kiswahili Literature', 'level': 200, 'semester': 2},
            {'code': 'KISW 302', 'name': 'Intermediate Kiswahili Usage II', 'level': 300, 'semester': 2},
            {'code': 'KISW 304', 'name': 'Comprehension and Oral Expression II', 'level': 300, 'semester': 2},
            {'code': 'KISW 306', 'name': 'Translation Exercises', 'level': 300, 'semester': 2},
            {'code': 'KISW 312', 'name': 'Kiswahili Oral Literature', 'level': 300, 'semester': 2},
            {'code': 'KISW 402', 'name': 'Advanced Kiswahili Proficiency II', 'level': 400, 'semester': 2},
            {'code': 'KISW 404', 'name': 'Advanced Oral Expression', 'level': 400, 'semester': 2},
            {'code': 'KISW 406', 'name': 'Advanced Kiswahili Translation II', 'level': 400, 'semester': 2},
            {'code': 'KISW 414', 'name': 'Contemporary Kiswahili Literature', 'level': 400, 'semester': 2},
            {'code': 'KISW 420', 'name': 'Study Abroad', 'level': 400, 'semester': 2},
        ]
        
        created_count = 0
        session_count = 0
        
        for course_data in courses:
            level_obj = level_map[course_data['level']]
            semester_obj = semester_map[course_data['semester']]
            
            course = Course.objects.create(
                code=course_data['code'],
                name=course_data['name'],
                level=level_obj,
                semester=semester_obj
            )
            created_count += 1
            self.stdout.write(f'✓ Created: {course.code} | {course.name}')
            
            # Generate 12 weekly sessions
            start_date = semester_obj.start_date
            for week_num in range(1, 13):
                session_date = start_date + timedelta(days=(week_num - 1) * 7)
                
                ClassSession.objects.create(
                    course=course,
                    date=session_date,
                    topic=f'Week {week_num}: {course.name}',
                    lecturer=lecturer  # This is a User object, not a string
                )
                session_count += 1
        
        self.stdout.write(self.style.SUCCESS(
            f'\n✅ COMPLETE!\n'
            f'   - {created_count} courses created\n'
            f'   - {session_count} class sessions generated'
        ))