from django.db import connection, models
from psycopg2 import sql


class SemesterAnalytics(models.Model):
    semester_id = models.IntegerField(primary_key=True)
    num_courses = models.IntegerField()
    num_unique_students = models.IntegerField()
    num_subscriptions = models.IntegerField()

    @classmethod
    def refresh_view(cls):
        _refresh_materialized_view(cls._meta.db_table)

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

    @classmethod
    def refresh_view(cls):
        _refresh_materialized_view(cls._meta.db_table)

    class Meta:
        managed = False
        db_table = "materialized_top_courses"
        unique_together = ("semester_id", "course_id")
        ordering = ["semester_id", "-subscription_count"]


class SubscriptionsCount(models.Model):
    count = models.IntegerField()
    date = models.DateField(primary_key=True)

    @classmethod
    def refresh_view(cls):
        _refresh_materialized_view(cls._meta.db_table)

    class Meta:
        managed = False
        db_table = "materialzed_subscriptions_count"
        ordering = ["date"]


def _refresh_materialized_view(name):
    query = sql.SQL("REFRESH MATERIALIZED VIEW CONCURRENTLY {}")
    query = query.format(sql.Identifier(name))

    with connection.cursor() as cursor:
        cursor.execute(query)
