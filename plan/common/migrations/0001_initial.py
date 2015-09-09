# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='Course',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('code', models.CharField(max_length=100, verbose_name='Code')),
                ('name', models.TextField(verbose_name='Name')),
                ('version', models.CharField(max_length=20, null=True, verbose_name='Version')),
                ('url', models.URLField(verbose_name='URL')),
                ('syllabus', models.URLField(verbose_name='URL')),
                ('points', models.DecimalField(null=True, verbose_name='Points', max_digits=5, decimal_places=2)),
                ('last_import', models.DateTimeField(auto_now=True, verbose_name='Last import time')),
            ],
            options={
                'verbose_name': 'Course',
                'verbose_name_plural': 'Courses',
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='Deadline',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('task', models.CharField(max_length=255, verbose_name='Task')),
                ('date', models.DateField(verbose_name='Due date')),
                ('time', models.TimeField(null=True, verbose_name='Time')),
                ('done', models.DateTimeField(null=True, verbose_name='Done')),
            ],
            options={
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='Exam',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('combination', models.CharField(max_length=50, null=True, verbose_name='Combination')),
                ('exam_date', models.DateField(null=True, verbose_name='Exam date')),
                ('exam_time', models.TimeField(null=True, verbose_name='Exam time')),
                ('handout_date', models.DateField(null=True, verbose_name='Handout date')),
                ('handout_time', models.TimeField(null=True, verbose_name='Handout time')),
                ('duration', models.DecimalField(help_text='Duration in hours', null=True, verbose_name='Duration', max_digits=5, decimal_places=2)),
                ('url', models.URLField(default=b'', verbose_name='URL')),
                ('last_import', models.DateTimeField(auto_now=True, verbose_name='Last import time')),
                ('course', models.ForeignKey(to='common.Course')),
            ],
            options={
                'verbose_name': 'Exam',
                'verbose_name_plural': 'Exams',
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='ExamType',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('code', models.CharField(unique=True, max_length=20, verbose_name='Code')),
                ('name', models.CharField(max_length=100, null=True, verbose_name='Name')),
                ('last_import', models.DateTimeField(auto_now=True, verbose_name='Last import time')),
            ],
            options={
                'verbose_name': 'Exam type',
                'verbose_name_plural': 'Exam types',
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='Group',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('code', models.CharField(max_length=20, unique=True, null=True, verbose_name='Code')),
                ('name', models.CharField(max_length=100, null=True, verbose_name='Name')),
                ('url', models.URLField(default=b'', verbose_name='URL')),
            ],
            options={
                'verbose_name': 'Group',
                'verbose_name_plural': 'Groups',
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='Lecture',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('day', models.PositiveSmallIntegerField(verbose_name='Week day', choices=[(0, 'Monday'), (1, 'Tuesday'), (2, 'Wednesday'), (3, 'Thursday'), (4, 'Friday')])),
                ('start', models.TimeField(verbose_name='Start time')),
                ('end', models.TimeField(verbose_name='End time')),
                ('last_import', models.DateTimeField(auto_now=True, verbose_name='Last import time')),
                ('course', models.ForeignKey(to='common.Course')),
                ('groups', models.ManyToManyField(to='common.Group', null=True)),
            ],
            options={
                'verbose_name': 'Lecture',
                'verbose_name_plural': 'Lecture',
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='Lecturer',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('name', models.CharField(unique=True, max_length=200, verbose_name='Name')),
            ],
            options={
                'verbose_name': 'Lecturer',
                'verbose_name_plural': 'Lecturers',
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='LectureType',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('code', models.CharField(max_length=20, unique=True, null=True, verbose_name='Code')),
                ('name', models.CharField(unique=True, max_length=100, verbose_name='Name')),
                ('optional', models.BooleanField(verbose_name='Optional')),
            ],
            options={
                'verbose_name': 'Lecture type',
                'verbose_name_plural': 'Lecture types',
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='Room',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('code', models.CharField(max_length=20, unique=True, null=True, verbose_name='Code')),
                ('name', models.CharField(max_length=100, verbose_name='Name')),
                ('url', models.URLField(default=b'', verbose_name='URL')),
                ('last_import', models.DateTimeField(auto_now=True, verbose_name='Last import time')),
            ],
            options={
                'verbose_name': 'Room',
                'verbose_name_plural': 'Rooms',
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='Semester',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('year', models.PositiveSmallIntegerField(verbose_name='Year')),
                ('type', models.CharField(max_length=10, verbose_name='Type', choices=[(b'spring', 'spring'), (b'fall', 'fall')])),
                ('active', models.DateField(null=True, verbose_name='Active')),
            ],
            options={
                'verbose_name': 'Semester',
                'verbose_name_plural': 'Semesters',
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='Student',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('slug', models.SlugField(unique=True, verbose_name='Slug')),
                ('show_deadlines', models.BooleanField(default=False, verbose_name='Show deadlines')),
            ],
            options={
                'verbose_name': 'Student',
                'verbose_name_plural': 'Students',
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='Subscription',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('alias', models.CharField(max_length=50, verbose_name='Alias', blank=True)),
                ('added', models.DateTimeField(auto_now_add=True, verbose_name='Added')),
                ('course', models.ForeignKey(to='common.Course')),
                ('exclude', models.ManyToManyField(related_name='excluded_from', null=True, to='common.Lecture')),
                ('groups', models.ManyToManyField(to='common.Group', null=True)),
                ('student', models.ForeignKey(to='common.Student')),
            ],
            options={
                'verbose_name': 'Subscription',
                'verbose_name_plural': 'Subscriptions',
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='Week',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('number', models.PositiveIntegerField(verbose_name='Week number', choices=[(1, 1), (2, 2), (3, 3), (4, 4), (5, 5), (6, 6), (7, 7), (8, 8), (9, 9), (10, 10), (11, 11), (12, 12), (13, 13), (14, 14), (15, 15), (16, 16), (17, 17), (18, 18), (19, 19), (20, 20), (21, 21), (22, 22), (23, 23), (24, 24), (25, 25), (26, 26), (27, 27), (28, 28), (29, 29), (30, 30), (31, 31), (32, 32), (33, 33), (34, 34), (35, 35), (36, 36), (37, 37), (38, 38), (39, 39), (40, 40), (41, 41), (42, 42), (43, 43), (44, 44), (45, 45), (46, 46), (47, 47), (48, 48), (49, 49), (50, 50), (51, 51), (52, 52)])),
                ('lecture', models.ForeignKey(related_name='weeks', to='common.Lecture')),
            ],
            options={
                'verbose_name': 'Lecture week',
                'verbose_name_plural': 'Lecture weeks',
            },
            bases=(models.Model,),
        ),
        migrations.AlterUniqueTogether(
            name='week',
            unique_together=set([('lecture', 'number')]),
        ),
        migrations.AlterUniqueTogether(
            name='subscription',
            unique_together=set([('student', 'course')]),
        ),
        migrations.AlterUniqueTogether(
            name='semester',
            unique_together=set([('year', 'type')]),
        ),
        migrations.AlterUniqueTogether(
            name='room',
            unique_together=set([('code', 'name')]),
        ),
        migrations.AddField(
            model_name='lecture',
            name='lecturers',
            field=models.ManyToManyField(to='common.Lecturer', null=True),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='lecture',
            name='rooms',
            field=models.ManyToManyField(to='common.Room', null=True),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='lecture',
            name='type',
            field=models.ForeignKey(to='common.LectureType', null=True),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='exam',
            name='type',
            field=models.ForeignKey(to='common.ExamType', null=True),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='deadline',
            name='subscription',
            field=models.ForeignKey(to='common.Subscription'),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='course',
            name='semester',
            field=models.ForeignKey(to='common.Semester'),
            preserve_default=True,
        ),
        migrations.AlterUniqueTogether(
            name='course',
            unique_together=set([('code', 'semester', 'version')]),
        ),
    ]
