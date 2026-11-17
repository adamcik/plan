from django.db import models


class SnapshotImportRun(models.Model):
    """Audit of one decode-and-import attempt, not a copy of source payloads.

    Successful rows commit with the imported data, so they also establish the
    latest accepted capture-start watermark for a semester, even when acquisition
    is resumed. Failed attempts survive import rollback; the immutable archive
    remains the replay source, not this audit row.
    """

    id = models.AutoField(primary_key=True)
    snapshot_id = models.UUIDField(db_index=True)
    source_name = models.TextField()
    source_format_version = models.PositiveIntegerField()
    content_sha256 = models.CharField(max_length=64)
    year = models.PositiveSmallIntegerField()
    type = models.CharField(max_length=10)
    schema_version = models.PositiveIntegerField()
    captured_at = models.DateTimeField()
    started_at = models.DateTimeField(auto_now_add=True)
    finished_at = models.DateTimeField(null=True)
    status = models.CharField(
        max_length=10,
        choices=[
            ("running", "running"),
            ("succeeded", "succeeded"),
            ("failed", "failed"),
        ],
    )
    diff = models.JSONField(default=dict)
    error = models.TextField(default="")

    class Meta:
        indexes = (models.Index(fields=["year", "type", "status", "captured_at"]),)
