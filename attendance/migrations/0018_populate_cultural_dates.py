from django.db import migrations


CULTURAL_DATES = [
    {
        'name': 'World Swahili Language Day',
        'day': 7,
        'month': 7,
        'emoji': '🌍',
        'description': (
            'Leo ni Siku ya Lugha ya Kiswahili Duniani! Tunaadhimisha utajiri wa lugha yetu ya Kiswahili. '
            'Kiswahili ni lugha ya Waafrika — inayounganisha mataifa zaidi ya watu milioni 200! '
            '(Today is World Swahili Language Day! We celebrate the richness of our Kiswahili language. '
            'Swahili is Africa\'s language — connecting over 200 million people!)'
        ),
    },
    {
        'name': 'International Mother Language Day',
        'day': 21,
        'month': 2,
        'emoji': '📚',
        'description': (
            'Leo ni Siku ya Kimataifa ya Lugha ya Mama! UNESCO ilianzisha siku hii mwaka 1999 kukumbuka '
            'umuhimu wa lugha zote duniani. Lugha yako ni utambulisho wako! '
            '(Today is International Mother Language Day! UNESCO established this day in 1999 to recognize '
            'the importance of all languages. Your language is your identity!)'
        ),
    },
    {
        'name': 'European Day of Languages',
        'day': 26,
        'month': 9,
        'emoji': '🗣️',
        'description': (
            'Today is the European Day of Languages! As Swahili students, you are part of a global community '
            'of language learners. Speaking multiple languages opens doors across the world!'
        ),
    },
    {
        'name': 'World Swahili Writers Day',
        'day': 11,
        'month': 4,
        'emoji': '✍️',
        'description': (
            'Leo ni Siku ya Waandishi wa Kiswahili Duniani! Tunaadhimisha waandishi wote wanaolinda na kukuza '
            'fasihi ya Kiswahili. Je, wewe ni mwandishi wa kesho? '
            '(Today is World Swahili Writers Day! We celebrate all writers who preserve and promote Swahili '
            'literature. Are you tomorrow\'s writer?)'
        ),
    },
    {
        'name': 'African Languages Month Begins',
        'day': 1,
        'month': 10,
        'emoji': '🌍',
        'description': (
            'Mwezi wa Lugha za Kiafrika unaanza leo! Kwa mwezi mzima tutaadhimisha utajiri wa lugha za bara '
            'la Afrika. Kiswahili ni moja ya lugha za Afrika zinazokua haraka zaidi! '
            '(African Languages Month begins today! For the whole month we celebrate the richness of African '
            'languages. Swahili is one of Africa\'s fastest growing languages!)'
        ),
    },
    {
        'name': 'International Day of La Francophonie',
        'day': 20,
        'month': 3,
        'emoji': '🇫🇷',
        'description': (
            'Today is the International Day of La Francophonie! As students of languages at the University '
            'of Ghana, we celebrate all languages and their cultures. Every language is a window into a '
            'different world!'
        ),
    },
    {
        'name': 'Arabic Language Day',
        'day': 18,
        'month': 12,
        'emoji': '🌙',
        'description': (
            'Today is Arabic Language Day! Arabic is one of the world\'s oldest and most beautiful languages, '
            'and a sister language to many Swahili words. Kiswahili has over 20% of its vocabulary from '
            'Arabic roots!'
        ),
    },
]


def populate_cultural_dates(apps, schema_editor):
    CulturalDate = apps.get_model('attendance', 'CulturalDate')
    for d in CULTURAL_DATES:
        CulturalDate.objects.get_or_create(
            day=d['day'],
            month=d['month'],
            name=d['name'],
            defaults={
                'description': d['description'],
                'emoji': d['emoji'],
                'is_active': True,
            },
        )


def remove_cultural_dates(apps, schema_editor):
    CulturalDate = apps.get_model('attendance', 'CulturalDate')
    names = [d['name'] for d in CULTURAL_DATES]
    CulturalDate.objects.filter(name__in=names).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('attendance', '0017_culturaldate_systemnotification'),
    ]

    operations = [
        migrations.RunPython(populate_cultural_dates, remove_cultural_dates),
    ]
