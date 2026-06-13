# Hand-written data migration.
#
# Copies every existing UserProfile.registered_courses link (the auto-created
# M2M junction rows) into the new explicit CourseRegistration table, marking
# each as active. This MUST run while registered_courses is still a plain M2M
# (i.e. before 0023 adds through=CourseRegistration), so the historical
# manager below can still read the old junction table.
#
# No rows are deleted on the forward path — existing data is only ever read
# and duplicated into the new table.

from django.db import migrations


def copy_registrations(apps, schema_editor):
    """Forward: create one active CourseRegistration per existing M2M link."""
    UserProfile = apps.get_model('attendance', 'UserProfile')
    CourseRegistration = apps.get_model('attendance', 'CourseRegistration')

    for profile in UserProfile.objects.all():
        # At this migration state, registered_courses is still a plain M2M,
        # so .all() reads from the old auto-created junction table.
        for course in profile.registered_courses.all():
            # get_or_create keeps the migration idempotent and respects the
            # (user_profile, course) unique constraint. registered_at is set
            # automatically by auto_now_add (no original timestamp exists).
            CourseRegistration.objects.get_or_create(
                user_profile=profile,
                course=course,
                defaults={'is_active': True},
            )


def restore_registrations(apps, schema_editor):
    """Reverse: rebuild the plain M2M links from CourseRegistration, then drop
    the through rows.

    Reverse runs AFTER 0023 has been reversed, so registered_courses is once
    again a plain M2M backed by an (empty) auto junction table. We restore only
    ACTIVE registrations, because a plain M2M cannot express the inactive/
    deregistered state. The inactive audit rows are therefore lost on a full
    down-migration — acceptable for a local dev rollback, and the only option
    a plain M2M allows.
    """
    UserProfile = apps.get_model('attendance', 'UserProfile')
    CourseRegistration = apps.get_model('attendance', 'CourseRegistration')

    for reg in CourseRegistration.objects.filter(is_active=True).select_related(
        'user_profile', 'course'
    ):
        reg.user_profile.registered_courses.add(reg.course)

    CourseRegistration.objects.all().delete()


class Migration(migrations.Migration):

    dependencies = [
        ('attendance', '0021_add_course_registration_model'),
    ]

    operations = [
        migrations.RunPython(copy_registrations, restore_registrations),
    ]
