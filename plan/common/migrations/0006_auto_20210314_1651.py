# -*- coding: utf-8 -*-
# Generated by Django 1.11.27 on 2021-03-14 16:51
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('common', '0005_lecture_title'),
    ]

    operations = [
        migrations.AlterField(
            model_name='room',
            name='url',
            field=models.URLField(default=b'', max_length=500, verbose_name='URL'),
        ),
    ]
