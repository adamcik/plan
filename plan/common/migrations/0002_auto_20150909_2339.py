# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('common', '0001_initial'),
    ]

    operations = [
        migrations.AlterField(
            model_name='lecturetype',
            name='optional',
            field=models.BooleanField(default=False, verbose_name='Optional'),
            preserve_default=True,
        ),
    ]
