# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('common', '0003_auto_20150910_0100'),
    ]

    operations = [
        migrations.AlterField(
            model_name='room',
            name='code',
            field=models.CharField(max_length=100, unique=True, null=True, verbose_name='Code'),
        ),
    ]
