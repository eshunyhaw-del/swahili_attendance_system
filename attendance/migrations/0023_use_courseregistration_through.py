# Hand-written swap migration.
#
# Django cannot ALTER an existing M2M to add through= at the database level
# (it raises "you cannot ... add or remove through= on M2M fields"). So we use
# SeparateDatabaseAndState:
#   * STATE    — tell Django the M2M now routes through CourseRegistration.
#   * DATABASE — only drop the now-orphaned auto junction table. The real data
#                already lives in attendance_courseregistration (copied in 0022
#                and verified), so dropping this table loses nothing.
#
# The reverse recreates the old junction table (empty); 0022's reverse then
# repopulates it from CourseRegistration. DDL below is copied verbatim from the
# live SQLite schema so the recreated table matches the original exactly.

from django.db import migrations, models


DROP_OLD_JUNCTION = 'DROP TABLE "attendance_userprofile_registered_courses";'

RECREATE_OLD_JUNCTION = [
    'CREATE TABLE "attendance_userprofile_registered_courses" '
    '("id" integer NOT NULL PRIMARY KEY AUTOINCREMENT, '
    '"userprofile_id" bigint NOT NULL REFERENCES "attendance_userprofile" ("id") DEFERRABLE INITIALLY DEFERRED, '
    '"course_id" bigint NOT NULL REFERENCES "attendance_course" ("id") DEFERRABLE INITIALLY DEFERRED);',

    'CREATE UNIQUE INDEX "attendance_userprofile_registered_courses_userprofile_id_course_id_c00c14f5_uniq" '
    'ON "attendance_userprofile_registered_courses" ("userprofile_id", "course_id");',

    'CREATE INDEX "attendance_userprofile_registered_courses_userprofile_id_c811e48d" '
    'ON "attendance_userprofile_registered_courses" ("userprofile_id");',

    'CREATE INDEX "attendance_userprofile_registered_courses_course_id_b514132c" '
    'ON "attendance_userprofile_registered_courses" ("course_id");',
]


class Migration(migrations.Migration):

    dependencies = [
        ('attendance', '0022_copy_registrations_to_through'),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.AlterField(
                    model_name='userprofile',
                    name='registered_courses',
                    field=models.ManyToManyField(
                        blank=True,
                        related_name='registered_students',
                        through='attendance.CourseRegistration',
                        to='attendance.course',
                    ),
                ),
            ],
            database_operations=[
                migrations.RunSQL(
                    sql=DROP_OLD_JUNCTION,
                    reverse_sql=RECREATE_OLD_JUNCTION,
                ),
            ],
        ),
    ]
