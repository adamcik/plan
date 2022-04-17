from django.db import migrations


def forwards(apps, schema_editor):
    Course = apps.get_model('common', 'Course')
    Location = apps.get_model('common', 'Location')

    Location.objects.create(name='Trondheim').course_set.set(Course.objects.all())


class Migration(migrations.Migration):

    dependencies = [
        ('common', '0003_course_locations'),
    ]

    operations = [
        migrations.RunPython(forwards),
    ]
