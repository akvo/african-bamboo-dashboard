import uuid

from django.db import models
from api.v1.v1_odk.constants import ApprovalStatusTypes


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
        max_length=255,
        null=True,
        blank=True,
        help_text=(
            "Comma-separated field names for "
            "region. Non-empty values joined "
            "with ' - '."
        ),
    )
    sub_region_field = models.CharField(
        max_length=255,
        null=True,
        blank=True,
        help_text=(
            "Comma-separated field names for "
            "sub-region. Non-empty values "
            "joined with ' - '."
        ),
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
    APPROVED = ApprovalStatusTypes.APPROVED, "Approved"
    REJECTED = ApprovalStatusTypes.REJECTED, "Not approved"


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
    flagged_for_review = models.BooleanField(
        null=True,
        default=None,
        help_text=(
            "NULL = not yet checked, "
            "False = checked and clean, "
            "True = flagged for review."
        ),
    )
    flagged_reason = models.CharField(
        max_length=500,
        null=True,
        blank=True,
        help_text="Reason for flagging the plot for review",
    )

    class Meta:
        db_table = "plots"

    def __str__(self):
        return self.plot_name


class FormQuestion(models.Model):
    form = models.ForeignKey(
        FormMetadata,
        on_delete=models.CASCADE,
        related_name="questions",
    )
    name = models.CharField(
        max_length=125,
        help_text="Unique question name within the form",
    )
    label = models.CharField(
        max_length=500,
        help_text="Question label shown to users",
    )
    type = models.CharField(
        max_length=125,
        help_text="Question type, e.g. text, integer, select_one etc.",
    )

    class Meta:
        db_table = "form_questions"
        unique_together = ("form", "name")
        verbose_name_plural = "form questions"

    def __str__(self):
        return f"{self.form.asset_uid} - {self.name}"


# For select_one and select_multiple questions,
# we store options in a separate table.
# grouped by list_name in the form content.
# This allows us to easily query option labels when processing submissions.
# For other question types, there are no options and this table is not used.
class FormOption(models.Model):
    question = models.ForeignKey(
        FormQuestion,
        on_delete=models.CASCADE,
        related_name="options",
    )
    name = models.CharField(
        max_length=125,
        help_text="Option value stored in submission",
    )
    label = models.CharField(
        max_length=500,
        help_text="Option label shown to users",
    )

    class Meta:
        db_table = "form_options"
        verbose_name_plural = "form options"

    def __str__(self):
        return (
            f"{self.question.form.asset_uid} - "
            f"{self.question.name} - {self.name}"
        )
