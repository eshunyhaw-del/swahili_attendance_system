import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('attendance', '0015_add_notification_model'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name='tannouncement',
            name='course',
            field=models.ForeignKey(
                blank=True, null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='announcements',
                to='attendance.course',
            ),
        ),
        migrations.AddField(
            model_name='tannouncement',
            name='is_active',
            field=models.BooleanField(default=True),
        ),
        migrations.CreateModel(
            name='StudentNotification',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('is_read', models.BooleanField(default=False)),
                ('read_at', models.DateTimeField(blank=True, null=True)),
                ('student', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='announcement_notifications',
                    to=settings.AUTH_USER_MODEL,
                )),
                ('announcement', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='student_notifications',
                    to='attendance.tannouncement',
                )),
            ],
            options={
                'ordering': ['-announcement__sent_at'],
            },
        ),
    ]
