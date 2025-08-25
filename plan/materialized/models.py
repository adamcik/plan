from django.db import models


class SemesterAnalytics(models.Model):
    semester_id = models.IntegerField(primary_key=True)
    num_courses = models.IntegerField()
    num_unique_students = models.IntegerField()
    num_subscriptions = models.IntegerField()

    class Meta:
        managed = False
        db_table = "materialized_semester_analytics"
        ordering = ["semester_id"]


class TopCourses(models.Model):
    semester_id = models.IntegerField()
    course_id = models.IntegerField()
    course_code = models.CharField(max_length=100)
    course_name = models.TextField()
    subscription_count = models.IntegerField()
    rank_in_semester = models.IntegerField()

    # This is a fake key that does not exist in the view.
    django_pk = models.AutoField(primary_key=True)

    class Meta:
        managed = False
        db_table = "materialized_top_courses"
        unique_together = ("semester_id", "course_id")
        ordering = ["semester_id", "-subscription_count"]


class SubscriptionsCount(models.Model):
    count = models.IntegerField()
    date = models.DateField(primary_key=True)

    class Meta:
        managed = False
        db_table = "materialzed_subscriptions_count"
        ordering = ["date"]
