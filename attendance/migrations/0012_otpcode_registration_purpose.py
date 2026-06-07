from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('attendance', '0011_otpcode'),
    ]

    operations = [
        migrations.AlterField(
            model_name='otpcode',
            name='purpose',
            field=models.CharField(
                choices=[
                    ('login', 'Login'),
                    ('password_reset', 'Password Reset'),
                    ('registration', 'Registration'),
                ],
                max_length=20,
            ),
        ),
    ]
