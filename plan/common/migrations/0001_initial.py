# Generated by Django 1.11.27 on 2019-12-30 22:25

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="Course",
            fields=[
                (
                    "id",
                    models.AutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("code", models.CharField(max_length=100, verbose_name="Code")),
                ("name", models.TextField(verbose_name="Name")),
                (
                    "version",
                    models.CharField(max_length=20, null=True, verbose_name="Version"),
                ),
                ("url", models.URLField(verbose_name="URL")),
                ("syllabus", models.URLField(verbose_name="URL")),
                (
                    "points",
                    models.DecimalField(
                        decimal_places=2, max_digits=5, null=True, verbose_name="Points"
                    ),
                ),
                (
                    "last_import",
                    models.DateTimeField(
                        auto_now=True, verbose_name="Last import time"
                    ),
                ),
            ],
            options={
                "verbose_name": "Course",
                "verbose_name_plural": "Courses",
            },
        ),
        migrations.CreateModel(
            name="Deadline",
            fields=[
                (
                    "id",
                    models.AutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("task", models.CharField(max_length=255, verbose_name="Task")),
                ("date", models.DateField(verbose_name="Due date")),
                ("time", models.TimeField(null=True, verbose_name="Time")),
                ("done", models.DateTimeField(null=True, verbose_name="Done")),
            ],
        ),
        migrations.CreateModel(
            name="Exam",
            fields=[
                (
                    "id",
                    models.AutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "combination",
                    models.CharField(
                        max_length=50, null=True, verbose_name="Combination"
                    ),
                ),
                ("exam_date", models.DateField(null=True, verbose_name="Exam date")),
                ("exam_time", models.TimeField(null=True, verbose_name="Exam time")),
                (
                    "handout_date",
                    models.DateField(null=True, verbose_name="Handout date"),
                ),
                (
                    "handout_time",
                    models.TimeField(null=True, verbose_name="Handout time"),
                ),
                (
                    "duration",
                    models.DecimalField(
                        decimal_places=2,
                        help_text="Duration in hours",
                        max_digits=5,
                        null=True,
                        verbose_name="Duration",
                    ),
                ),
                ("url", models.URLField(default=b"", verbose_name="URL")),
                (
                    "last_import",
                    models.DateTimeField(
                        auto_now=True, verbose_name="Last import time"
                    ),
                ),
                (
                    "course",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE, to="common.Course"
                    ),
                ),
            ],
            options={
                "verbose_name": "Exam",
                "verbose_name_plural": "Exams",
            },
        ),
        migrations.CreateModel(
            name="ExamType",
            fields=[
                (
                    "id",
                    models.AutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "code",
                    models.CharField(max_length=20, unique=True, verbose_name="Code"),
                ),
                (
                    "name",
                    models.CharField(max_length=100, null=True, verbose_name="Name"),
                ),
                (
                    "last_import",
                    models.DateTimeField(
                        auto_now=True, verbose_name="Last import time"
                    ),
                ),
            ],
            options={
                "verbose_name": "Exam type",
                "verbose_name_plural": "Exam types",
            },
        ),
        migrations.CreateModel(
            name="Group",
            fields=[
                (
                    "id",
                    models.AutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "code",
                    models.CharField(
                        max_length=20, null=True, unique=True, verbose_name="Code"
                    ),
                ),
                (
                    "name",
                    models.CharField(max_length=100, null=True, verbose_name="Name"),
                ),
                ("url", models.URLField(default=b"", verbose_name="URL")),
            ],
            options={
                "verbose_name": "Group",
                "verbose_name_plural": "Groups",
            },
        ),
        migrations.CreateModel(
            name="Lecture",
            fields=[
                (
                    "id",
                    models.AutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "day",
                    models.PositiveSmallIntegerField(
                        choices=[
                            (0, "Monday"),
                            (1, "Tuesday"),
                            (2, "Wednesday"),
                            (3, "Thursday"),
                            (4, "Friday"),
                        ],
                        verbose_name="Week day",
                    ),
                ),
                ("start", models.TimeField(verbose_name="Start time")),
                ("end", models.TimeField(verbose_name="End time")),
                (
                    "last_import",
                    models.DateTimeField(
                        auto_now=True, verbose_name="Last import time"
                    ),
                ),
                (
                    "course",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE, to="common.Course"
                    ),
                ),
                ("groups", models.ManyToManyField(to="common.Group")),
            ],
            options={
                "verbose_name": "Lecture",
                "verbose_name_plural": "Lecture",
            },
        ),
        migrations.CreateModel(
            name="Lecturer",
            fields=[
                (
                    "id",
                    models.AutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "name",
                    models.CharField(max_length=200, unique=True, verbose_name="Name"),
                ),
            ],
            options={
                "verbose_name": "Lecturer",
                "verbose_name_plural": "Lecturers",
            },
        ),
        migrations.CreateModel(
            name="LectureType",
            fields=[
                (
                    "id",
                    models.AutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "code",
                    models.CharField(
                        max_length=20, null=True, unique=True, verbose_name="Code"
                    ),
                ),
                (
                    "name",
                    models.CharField(max_length=100, unique=True, verbose_name="Name"),
                ),
                (
                    "optional",
                    models.BooleanField(default=False, verbose_name="Optional"),
                ),
            ],
            options={
                "verbose_name": "Lecture type",
                "verbose_name_plural": "Lecture types",
            },
        ),
        migrations.CreateModel(
            name="Room",
            fields=[
                (
                    "id",
                    models.AutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "code",
                    models.CharField(
                        max_length=100, null=True, unique=True, verbose_name="Code"
                    ),
                ),
                ("name", models.CharField(max_length=100, verbose_name="Name")),
                ("url", models.URLField(default=b"", verbose_name="URL")),
                (
                    "last_import",
                    models.DateTimeField(
                        auto_now=True, verbose_name="Last import time"
                    ),
                ),
            ],
            options={
                "verbose_name": "Room",
                "verbose_name_plural": "Rooms",
            },
        ),
        migrations.CreateModel(
            name="Semester",
            fields=[
                (
                    "id",
                    models.AutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("year", models.PositiveSmallIntegerField(verbose_name="Year")),
                (
                    "type",
                    models.CharField(
                        choices=[(b"spring", "spring"), (b"fall", "fall")],
                        max_length=10,
                        verbose_name="Type",
                    ),
                ),
                ("active", models.DateField(null=True, verbose_name="Active")),
            ],
            options={
                "verbose_name": "Semester",
                "verbose_name_plural": "Semesters",
            },
        ),
        migrations.CreateModel(
            name="Student",
            fields=[
                (
                    "id",
                    models.AutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("slug", models.SlugField(unique=True, verbose_name="Slug")),
                (
                    "show_deadlines",
                    models.BooleanField(default=False, verbose_name="Show deadlines"),
                ),
            ],
            options={
                "verbose_name": "Student",
                "verbose_name_plural": "Students",
            },
        ),
        migrations.CreateModel(
            name="Subscription",
            fields=[
                (
                    "id",
                    models.AutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "alias",
                    models.CharField(blank=True, max_length=50, verbose_name="Alias"),
                ),
                (
                    "added",
                    models.DateTimeField(auto_now_add=True, verbose_name="Added"),
                ),
                (
                    "course",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE, to="common.Course"
                    ),
                ),
                (
                    "exclude",
                    models.ManyToManyField(
                        related_name="excluded_from", to="common.Lecture"
                    ),
                ),
                ("groups", models.ManyToManyField(to="common.Group")),
                (
                    "student",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE, to="common.Student"
                    ),
                ),
            ],
            options={
                "verbose_name": "Subscription",
                "verbose_name_plural": "Subscriptions",
            },
        ),
        migrations.CreateModel(
            name="Week",
            fields=[
                (
                    "id",
                    models.AutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "number",
                    models.PositiveIntegerField(
                        choices=[
                            (1, 1),
                            (2, 2),
                            (3, 3),
                            (4, 4),
                            (5, 5),
                            (6, 6),
                            (7, 7),
                            (8, 8),
                            (9, 9),
                            (10, 10),
                            (11, 11),
                            (12, 12),
                            (13, 13),
                            (14, 14),
                            (15, 15),
                            (16, 16),
                            (17, 17),
                            (18, 18),
                            (19, 19),
                            (20, 20),
                            (21, 21),
                            (22, 22),
                            (23, 23),
                            (24, 24),
                            (25, 25),
                            (26, 26),
                            (27, 27),
                            (28, 28),
                            (29, 29),
                            (30, 30),
                            (31, 31),
                            (32, 32),
                            (33, 33),
                            (34, 34),
                            (35, 35),
                            (36, 36),
                            (37, 37),
                            (38, 38),
                            (39, 39),
                            (40, 40),
                            (41, 41),
                            (42, 42),
                            (43, 43),
                            (44, 44),
                            (45, 45),
                            (46, 46),
                            (47, 47),
                            (48, 48),
                            (49, 49),
                            (50, 50),
                            (51, 51),
                            (52, 52),
                        ],
                        verbose_name="Week number",
                    ),
                ),
                (
                    "lecture",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="weeks",
                        to="common.Lecture",
                    ),
                ),
            ],
            options={
                "verbose_name": "Lecture week",
                "verbose_name_plural": "Lecture weeks",
            },
        ),
        migrations.AlterUniqueTogether(
            name="semester",
            unique_together={("year", "type")},
        ),
        migrations.AlterUniqueTogether(
            name="room",
            unique_together={("code", "name")},
        ),
        migrations.AddField(
            model_name="lecture",
            name="lecturers",
            field=models.ManyToManyField(to="common.Lecturer"),
        ),
        migrations.AddField(
            model_name="lecture",
            name="rooms",
            field=models.ManyToManyField(to="common.Room"),
        ),
        migrations.AddField(
            model_name="lecture",
            name="type",
            field=models.ForeignKey(
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                to="common.LectureType",
            ),
        ),
        migrations.AddField(
            model_name="exam",
            name="type",
            field=models.ForeignKey(
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                to="common.ExamType",
            ),
        ),
        migrations.AddField(
            model_name="deadline",
            name="subscription",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE, to="common.Subscription"
            ),
        ),
        migrations.AddField(
            model_name="course",
            name="semester",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE, to="common.Semester"
            ),
        ),
        migrations.AlterUniqueTogether(
            name="week",
            unique_together={("lecture", "number")},
        ),
        migrations.AlterUniqueTogether(
            name="subscription",
            unique_together={("student", "course")},
        ),
        migrations.AlterUniqueTogether(
            name="course",
            unique_together={("code", "semester", "version")},
        ),
    ]
