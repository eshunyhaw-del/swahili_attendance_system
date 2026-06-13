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
# The database half is expressed as a plain RemoveField (NOT raw SQL). Inside
# SeparateDatabaseAndState.database_operations it runs against the pre-0023
# state, where registered_courses is still a plain M2M — so schema_editor emits
# the correct DROP TABLE for the auto junction table on EVERY backend (SQLite
# locally, MySQL in production). Its auto-reverse (add_field) recreates that
# junction table just as portably; 0022's reverse then repopulates it. This
# replaces the earlier hand-written SQLite-only DDL, which failed on MySQL.

from django.db import migrations, models


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
                # Forward: drop the orphaned auto junction table.
                # Reverse: RemoveField's auto-reverse re-creates it (empty),
                # both rendered per-backend by the schema editor.
                migrations.RemoveField(
                    model_name='userprofile',
                    name='registered_courses',
                ),
            ],
        ),
    ]
