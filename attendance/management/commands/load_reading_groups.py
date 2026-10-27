from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from attendance.models import Course
from attendance.reading_groups import load_groups, notify_members

# KISW 413 (Modern Kiswahili Drama): group and reading assignments from the lecturer.
KISW_413 = [
    (1, 'JOGOO KIJIJINI', ['Ofosu Nana Yaa G. Korangeng', 'Enoch Opare', 'Abdul-Rahman Nayo',
                           'Asamoah Mary-Ann', 'Awatey Annabella']),
    (2, 'NGUZO MAMA', ['Kelvin', 'Alexander Selacie Adomey', 'Clement Nii Kwate Quartey',
                       'Queen Manuella L.V. Tongar']),
    (3, 'MASHETANI', ['Hokey Joel', 'Adu Offeibea M.Y. Obeng', 'Christabel Adjoa Awortwe',
                      'Kyeremah Jessica Eirene Agyeiwa', "Abdullah Sa'adatu"]),
    (4, 'MASHETANI WAMERUDI', ['Owusu Ernest Ackom', 'Okyerefo Benjamin', 'Cann Daniella Anna',
                               'Musah Bintu Fatima']),
    (5, 'LINA UBANI', ['Umar Zainab', 'Nyame Joshua Ntamawa', 'Ayensu Felicty', 'Lartey Belinda']),
    (6, 'KIVULI KINAISHI', ['Ayim Bright', 'Juliet', 'Kwalla Brandon Nana Yankyira', 'Abbey Emylyte']),
]


class Command(BaseCommand):
    help = ("Load the KISW 413 reading groups, link each listed name to a registered student, and "
            "notify newly linked students. Safe to re-run (links new registrants, never re-notifies). "
            "Use --dry-run to preview.")

    def add_arguments(self, parser):
        parser.add_argument('--course', default='KISW 413')
        parser.add_argument('--no-notify', action='store_true', help='Link names but send no notifications')
        parser.add_argument('--dry-run', action='store_true')

    @transaction.atomic
    def handle(self, *args, **o):
        course = Course.objects.filter(code=o['course']).first()
        if not course:
            raise CommandError(f"No course {o['course']!r}.")
        lines, linked, unmatched = load_groups(course, KISW_413)
        for line in lines:
            self.stdout.write(line)
        sent = 0 if o['no_notify'] else notify_members(course)
        self.stdout.write(self.style.SUCCESS(
            f"{linked} name(s) linked, {unmatched} not found, {sent} notification(s) sent."))
        if unmatched:
            self.stdout.write(self.style.WARNING(
                "Fix NOT FOUND names in the admin (Reading group members), or re-run once those students register."))
        if o['dry_run']:
            transaction.set_rollback(True)
            self.stdout.write(self.style.WARNING('DRY RUN - nothing saved.'))
