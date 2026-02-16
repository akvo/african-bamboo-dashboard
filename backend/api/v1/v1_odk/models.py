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
    polygon_field = models.CharField(
        max_length=255,
        null=True,
        blank=True,
        help_text=(
            "Comma-separated field paths for "
            "polygon in ODK geoshape format. "
            "First non-empty match is used."
        ),
    )
    region_field = models.CharField(
        max_length=125,
        null=True,
        blank=True,
        help_text="Name of the field in the form that captures region",
    )
    sub_region_field = models.CharField(
        max_length=125,
        null=True,
        blank=True,
        help_text="Name of the field in the form that captures sub-region",
    )
    plot_name_field = models.CharField(
        max_length=255,
        null=True,
        blank=True,
        help_text=(
            "Comma-separated field names for "
            "plot name. Values joined with spaces."
        ),
    )

    class Meta:
        db_table = "form_metadata"
        verbose_name_plural = "form metadata"

    def __str__(self):
        return f"Form {self.asset_uid}"


class ApprovalStatus(models.IntegerChoices):
    APPROVED = 1, "Approved"
    REJECTED = 2, "Not approved"


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
    submitted_by = models.CharField(max_length=255, null=True, blank=True)
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
    approval_status = models.IntegerField(
        choices=ApprovalStatus.choices,
        null=True,
        blank=True,
        db_index=True,
        help_text="NULL means pending",
    )
    reviewer_notes = models.TextField(
        null=True,
        blank=True,
        help_text=("Notes from reviewer on " "approval or rejection"),
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
    instance_name = models.CharField(max_length=255, db_index=True)
    polygon_wkt = models.TextField(
        null=True,
        blank=True,
        help_text="Polygon in WKT format",
    )
    min_lat = models.FloatField(null=True, blank=True, db_index=True)
    max_lat = models.FloatField(null=True, blank=True, db_index=True)
    min_lon = models.FloatField(null=True, blank=True, db_index=True)
    max_lon = models.FloatField(null=True, blank=True, db_index=True)
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
        return self.plot_name
