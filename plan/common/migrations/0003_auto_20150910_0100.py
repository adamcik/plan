# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('common', '0002_auto_20150909_2339'),
    ]

    operations = [
        migrations.AlterField(
            model_name='lecture',
            name='groups',
            field=models.ManyToManyField(to='common.Group'),
        ),
        migrations.AlterField(
            model_name='lecture',
            name='lecturers',
            field=models.ManyToManyField(to='common.Lecturer'),
        ),
        migrations.AlterField(
            model_name='lecture',
            name='rooms',
            field=models.ManyToManyField(to='common.Room'),
        ),
        migrations.AlterField(
            model_name='subscription',
            name='exclude',
            field=models.ManyToManyField(related_name='excluded_from', to='common.Lecture'),
        ),
        migrations.AlterField(
            model_name='subscription',
            name='groups',
            field=models.ManyToManyField(to='common.Group'),
        ),
    ]
