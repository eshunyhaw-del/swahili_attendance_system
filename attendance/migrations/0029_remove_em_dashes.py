from django.db import migrations, models
from django.db.models import Value
from django.db.models.functions import Replace

EM = "\u2014"


def strip_em_dashes(apps, schema_editor):
    """Replace em dashes in stored text so no screen shows one."""
    for model in apps.get_app_config("attendance").get_models():
        for field in model._meta.get_fields():
            if isinstance(field, (models.CharField, models.TextField)):
                qs = model.objects.filter(**{field.name + "__contains": EM})
                qs.update(**{field.name: Replace(Replace(field.name, Value(" " + EM + " "), Value(" - ")), Value(EM), Value("-"))})


class Migration(migrations.Migration):

    dependencies = [("attendance", "0028_userprofile_is_graduate")]

    operations = [migrations.RunPython(strip_em_dashes, migrations.RunPython.noop)]
