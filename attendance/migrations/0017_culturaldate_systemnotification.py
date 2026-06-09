from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('attendance', '0016_tannouncement_course_studentnotification'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='CulturalDate',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=200)),
                ('description', models.TextField()),
                ('day', models.IntegerField()),
                ('month', models.IntegerField()),
                ('emoji', models.CharField(default='🌍', max_length=10)),
                ('is_active', models.BooleanField(default=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
            ],
            options={
                'ordering': ['month', 'day'],
            },
        ),
        migrations.AddIndex(
            model_name='culturaldate',
            index=models.Index(fields=['day', 'month', 'is_active'], name='att_cultdate_day_month_idx'),
        ),
        migrations.CreateModel(
            name='SystemNotification',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('title', models.CharField(max_length=200)),
                ('message', models.TextField()),
                ('emoji', models.CharField(default='🌍', max_length=10)),
                ('is_read', models.BooleanField(default=False)),
                ('read_at', models.DateTimeField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('notification_type', models.CharField(
                    choices=[('cultural_date', 'Cultural Date'), ('system', 'System')],
                    default='system',
                    max_length=20,
                )),
                ('user', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='system_notifications',
                    to=settings.AUTH_USER_MODEL,
                )),
            ],
            options={
                'ordering': ['-created_at'],
            },
        ),
        migrations.AddIndex(
            model_name='systemnotification',
            index=models.Index(fields=['user', 'is_read'], name='att_sysnotif_user_unread_idx'),
        ),
    ]
