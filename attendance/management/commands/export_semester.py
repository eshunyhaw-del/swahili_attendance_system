import csv
import os
from collections import defaultdict

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from attendance.models import AttendanceRecord, ClassSession, CourseRegistration, Semester


class Command(BaseCommand):
    help = ("Export a semester's attendance to two CSV files (per-session detail and per-student summary). "
            "Run BEFORE the year rollover, while student levels are still last year's.")

    def add_arguments(self, parser):
        parser.add_argument('--semester', help='Semester name contains this text (e.g. "Second")')
        parser.add_argument('--id', type=int, help='Semester id (overrides --semester)')
        parser.add_argument('--outdir', default='.', help='Folder for the CSV files (default: current folder)')

    def handle(self, *args, **o):
        qs = Semester.objects.all()
        if o['id']:
            qs = qs.filter(pk=o['id'])
        elif o['semester']:
            qs = qs.filter(name__icontains=o['semester'])
        else:
            raise CommandError('Give --semester "Second" or --id N. Semesters: ' +
                               '; '.join(f'{s.id}={s.name} {s.year}' for s in Semester.objects.all()))
        sem = qs.order_by('-year', '-id').first()
        if not sem:
            raise CommandError('Semester not found.')

        regs = (CourseRegistration.objects.filter(course__semester=sem)
                .select_related('user_profile__user', 'user_profile__level', 'course', 'course__level'))
        sessions = defaultdict(list)
        for s in ClassSession.objects.filter(course__semester=sem).order_by('date', 'start_time'):
            sessions[s.course_id].append(s)
        present = {(r.student_id, r.class_session_id): r for r in
                   AttendanceRecord.objects.filter(class_session__course__semester=sem)}

        stamp = timezone.localdate().isoformat()
        base = os.path.join(o['outdir'], f"swasa_{sem.name.replace(' ', '_')}_{sem.year}_{stamp}")
        detail_path, summary_path = base + '_detail.csv', base + '_summary.csv'
        n_detail = n_summary = 0
        with open(detail_path, 'w', newline='', encoding='utf-8-sig') as fd, \
             open(summary_path, 'w', newline='', encoding='utf-8-sig') as fs:
            d, s = csv.writer(fd), csv.writer(fs)
            d.writerow(['Student ID', 'Student Name', 'Level at export', 'Course Code', 'Course Name',
                        'Registration Active', 'Session Date', 'Start', 'Topic', 'Status', 'Submitted At'])
            s.writerow(['Student ID', 'Student Name', 'Level at export', 'Course Code', 'Course Name',
                        'Registration Active', 'Sessions Held', 'Attended', 'Absent', 'Attendance %'])
            for r in regs.order_by('course__code', 'user_profile__student_id_number'):
                p, u = r.user_profile, r.user_profile.user
                name = u.get_full_name() or u.username
                lvl = p.level.name if p.level else ('Graduate' if p.is_graduate else '')
                att = 0
                held = sessions.get(r.course_id, [])
                for sess in held:
                    rec = present.get((u.id, sess.id))
                    att += bool(rec)
                    d.writerow([p.student_id_number or '', name, lvl, r.course.code, r.course.name,
                                'Yes' if r.is_active else 'No', sess.date, sess.start_time.strftime('%H:%M'),
                                sess.topic, 'Present' if rec else 'Absent',
                                timezone.localtime(rec.submitted_at).strftime('%Y-%m-%d %H:%M') if rec else ''])
                    n_detail += 1
                pct = round(att / len(held) * 100, 1) if held else ''
                s.writerow([p.student_id_number or '', name, lvl, r.course.code, r.course.name,
                            'Yes' if r.is_active else 'No', len(held), att, len(held) - att, pct])
                n_summary += 1
        self.stdout.write(self.style.SUCCESS(
            f'{sem.name} {sem.year}: {n_summary} student-course rows, {n_detail} session rows.'))
        self.stdout.write(f'  {os.path.abspath(detail_path)}\n  {os.path.abspath(summary_path)}')
