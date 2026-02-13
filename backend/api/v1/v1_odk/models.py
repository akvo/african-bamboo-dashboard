import uuid

from django.db import models


class FormMetadata(models.Model):
    asset_uid = models.CharField(
        max_length=255,
        unique=True,
        db_index=True,
    )
    name = models.CharField(
        max_length=500,
        default="",
        help_text="Form display name",
    )
    last_sync_timestamp = models.BigIntegerField(
        default=0,
        help_text="Epoch ms of last successful sync",
    )

    class Meta:
        db_table = "form_metadata"
        verbose_name_plural = "form metadata"

    def __str__(self):
        return f"Form {self.asset_uid}"


class Submission(models.Model):
    uuid = models.CharField(
        max_length=255,
        unique=True,
        db_index=True,
    )
    form = models.ForeignKey(
        FormMetadata,
        on_delete=models.CASCADE,
        related_name="submissions",
    )
    kobo_id = models.CharField(max_length=255)
    submission_time = models.BigIntegerField(
        db_index=True,
        help_text="Epoch ms",
    )
    submitted_by = models.CharField(
        max_length=255, null=True, blank=True
    )
    instance_name = models.CharField(
        max_length=255,
        null=True,
        blank=True,
        db_index=True,
    )
    raw_data = models.JSONField(
        help_text="Full dynamic form JSON",
    )
    system_data = models.JSONField(
        null=True,
        blank=True,
        help_text="_geolocation, _tags, etc.",
    )

    class Meta:
        db_table = "submissions"
        ordering = ["-submission_time"]

    def __str__(self):
        return self.instance_name or self.uuid


class Plot(models.Model):
    uuid = models.CharField(
        max_length=255,
        unique=True,
        db_index=True,
        default=uuid.uuid4,
    )
    plot_name = models.CharField(
        max_length=500,
        help_text="Farmer full name",
    )
    instance_name = models.CharField(
        max_length=255, db_index=True
    )
    polygon_wkt = models.TextField(
        help_text="Polygon in WKT format",
    )
    min_lat = models.FloatField(db_index=True)
    max_lat = models.FloatField(db_index=True)
    min_lon = models.FloatField(db_index=True)
    max_lon = models.FloatField(db_index=True)
    is_draft = models.BooleanField(default=True)
    form = models.ForeignKey(
        FormMetadata,
        on_delete=models.CASCADE,
        related_name="plots",
    )
    region = models.CharField(max_length=255)
    sub_region = models.CharField(max_length=255)
    created_at = models.BigIntegerField(
        help_text="Epoch ms",
    )
    submission = models.OneToOneField(
        Submission,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="plot",
    )

    class Meta:
        db_table = "plots"

    def __str__(self):
        tag = "draft" if self.is_draft else "synced"
        return f"{self.plot_name} ({tag})"
