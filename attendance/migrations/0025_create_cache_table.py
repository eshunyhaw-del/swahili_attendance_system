"""Create the database-cache table used by the DatabaseCache backend.

Equivalent to running ``manage.py createcachetable swasa_cache_table``, but wired
into ``migrate`` so deploys don't need a separate step. Idempotent —
createcachetable skips the table if it already exists.
"""

from django.conf import settings
from django.core.management import call_command
from django.db import migrations


def create_cache_table(apps, schema_editor):
    location = settings.CACHES['default'].get('LOCATION', 'swasa_cache_table')
    call_command('createcachetable', location, database=schema_editor.connection.alias)


def drop_cache_table(apps, schema_editor):
    location = settings.CACHES['default'].get('LOCATION', 'swasa_cache_table')
    schema_editor.execute(f'DROP TABLE IF EXISTS "{location}"')


class Migration(migrations.Migration):

    dependencies = [
        ('attendance', '0024_alter_tacode_code'),
    ]

    operations = [
        migrations.RunPython(create_cache_table, drop_cache_table),
    ]
