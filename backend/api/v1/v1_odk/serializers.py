from urllib.parse import quote

from django.conf import settings
from rest_framework import serializers

from api.v1.v1_odk.constants import (
    ATTACHMENTS_FOLDER,
    EXCLUDED_QUESTION_TYPES,
    ApprovalStatusTypes,
    RejectionCategory,
)
from api.v1.v1_odk.models import (
    FormMetadata,
    FormQuestion,
    Plot,
    RejectionAudit,
    Submission,
)
from utils.custom_serializer_fields import (
    CustomCharField,
    CustomFloatField,
)


def build_option_lookup(form):
    """Build option lookup dicts for a form.

    Returns (option_map, type_map) where:
    - option_map = {question.name: {opt.name: opt.label}}
    - type_map = {question.name: question.type}
    """
    qs = FormQuestion.objects.filter(
        form=form,
        type__startswith="select_",
    ).prefetch_related("options")

    option_map = {}
    type_map = {}
    for q in qs:
        type_map[q.name] = q.type
        option_map[q.name] = {opt.name: opt.label for opt in q.options.all()}
    return option_map, type_map


def resolve_value(raw_value, options_dict, q_type):
    """Resolve a raw submission value to its label.

    For select_one: direct lookup.
    For select_multiple: split by space, resolve each,
    join with ', '.
    Returns raw value if no match found.
    """
    if raw_value is None:
        return None
    raw_str = str(raw_value)
    if q_type == "select_multiple":
        parts = raw_str.split(" ")
        resolved = [options_dict.get(p, p) for p in parts]
        return ", ".join(resolved)
    return options_dict.get(raw_str, raw_str)


class FormMetadataSerializer(serializers.ModelSerializer):
    submission_count = serializers.SerializerMethodField()

    class Meta:
        model = FormMetadata
        fields = [
            "asset_uid",
            "name",
            "last_sync_timestamp",
            "submission_count",
            "polygon_field",
            "region_field",
            "sub_region_field",
            "plot_name_field",
            "filter_fields",
        ]

    def get_submission_count(self, obj):
        return obj.submissions.count()


class SubmissionListSerializer(serializers.ModelSerializer):
    """Lightweight list — excludes raw_data."""

    form = serializers.CharField(source="form.asset_uid", read_only=True)
    region = serializers.SerializerMethodField()
    sub_region = serializers.SerializerMethodField()
    enumerator = serializers.SerializerMethodField()
    plot_name = serializers.CharField(source="plot.plot_name", read_only=True)
    resolved_data = (
        serializers.SerializerMethodField()
    )

    class Meta:
        model = Submission
        fields = [
            "uuid",
            "form",
            "kobo_id",
            "submission_time",
            "submitted_by",
            "instance_name",
            "enumerator",
            "region",
            "sub_region",
            "approval_status",
            "plot_name",
            "resolved_data",
        ]

    def get_resolved_data(self, obj):
        option_map = self.context.get(
            "option_lookup", {}
        )
        type_map = self.context.get(
            "type_map", {}
        )
        raw = obj.raw_data or {}
        resolved = dict(raw)
        for key, val in raw.items():
            if key in option_map and val is not None:
                resolved[key] = resolve_value(
                    val,
                    option_map[key],
                    type_map.get(key),
                )
        # Enrich attachments with local URLs
        attachments = raw.get(
            "_attachments", []
        )
        if attachments:
            key = settings.STORAGE_SECRET
            enriched = []
            for att in attachments:
                att_copy = dict(att)
                uid = att.get("uid")
                basename = att.get(
                    "media_file_basename",
                    "img.jpg",
                )
                ext = (
                    basename.rsplit(".", 1)[-1]
                    or "jpg"
                )
                if uid:
                    encoded_key = quote(
                        key, safe=""
                    )
                    att_copy["local_url"] = (
                        f"/storage"
                        f"/{ATTACHMENTS_FOLDER}"
                        f"/{obj.uuid}"
                        f"/{uid}.{ext}"
                        f"?key={encoded_key}"
                    )
                enriched.append(att_copy)
            resolved["_attachments"] = enriched
        return resolved

    def _resolve_field(self, obj, field_name):
        raw = obj.raw_data or {}
        raw_val = raw.get(field_name)
        if raw_val is None:
            return None
        option_map = self.context.get(
            "option_lookup", {}
        )
        type_map = self.context.get("type_map", {})
        opts = option_map.get(field_name)
        if opts:
            return resolve_value(
                raw_val, opts, type_map.get(field_name)
            )
        return raw_val

    def _resolve_fields(self, obj, field_spec):
        """Resolve comma-separated field spec.

        Each field is resolved via option_map if
        available. Non-empty resolved values are
        joined with ' - '.
        """
        fields = [
            f.strip()
            for f in field_spec.split(",")
            if f.strip()
        ]
        parts = []
        for field_name in fields:
            resolved = self._resolve_field(
                obj, field_name
            )
            if resolved is not None:
                val = str(resolved).strip()
                if val:
                    parts.append(val)
        return " - ".join(parts) if parts else None

    def get_region(self, obj):
        form = obj.form
        field_spec = form.region_field or "region"
        return self._resolve_fields(obj, field_spec)

    def get_sub_region(self, obj):
        form = obj.form
        field_spec = (
            form.sub_region_field or "sub_region"
        )
        return self._resolve_fields(obj, field_spec)

    def get_enumerator(self, obj):
        return self._resolve_field(obj, "enumerator_id")


class RejectionAuditSerializer(
    serializers.ModelSerializer
):
    reason_category_display = (
        serializers.CharField(
            source="get_reason_category_display",
            read_only=True,
        )
    )
    validator_name = serializers.CharField(
        source="validator.name",
        read_only=True,
        default=None,
    )

    class Meta:
        model = RejectionAudit
        fields = [
            "id",
            "reason_category",
            "reason_category_display",
            "reason_text",
            "rejected_at",
            "sync_status",
            "telegram_sent_at",
            "validator_name",
        ]
        read_only_fields = fields


class SubmissionDetailSerializer(
    serializers.ModelSerializer
):
    """Full serializer with raw_data."""

    form = serializers.CharField(
        source="form.asset_uid", read_only=True
    )
    resolved_data = (
        serializers.SerializerMethodField()
    )
    questions = (
        serializers.SerializerMethodField()
    )
    rejection_audits = RejectionAuditSerializer(
        many=True, read_only=True
    )
    reviewer_notes = (
        serializers.SerializerMethodField()
    )

    class Meta:
        model = Submission
        fields = "__all__"

    def get_reviewer_notes(self, obj):
        audit = (
            obj.rejection_audits.order_by(
                "-rejected_at"
            ).first()
        )
        if audit:
            return audit.reason_text
        return None

    def get_resolved_data(self, obj):
        option_map, type_map = build_option_lookup(
            obj.form
        )
        raw = obj.raw_data or {}
        resolved = dict(raw)
        for key, val in raw.items():
            if key in option_map and val is not None:
                resolved[key] = resolve_value(
                    val,
                    option_map[key],
                    type_map.get(key),
                )
        return resolved

    def get_questions(self, obj):
        form = obj.form
        mapped_fields = set()
        for spec in [
            form.region_field,
            form.sub_region_field,
            form.plot_name_field,
        ]:
            if spec:
                for f in spec.split(","):
                    stripped = f.strip()
                    if stripped:
                        mapped_fields.add(stripped)

        qs = (
            FormQuestion.objects.filter(form=form)
            .exclude(
                type__in=EXCLUDED_QUESTION_TYPES
            )
            .order_by("pk")
        )
        return [
            {
                "name": q.name,
                "label": q.label,
                "type": q.type,
            }
            for q in qs
            if q.name not in mapped_fields
        ]


class SubmissionUpdateSerializer(
    serializers.ModelSerializer
):
    """Restrict writable fields for approval."""

    approval_status = serializers.IntegerField(
        required=False,
        allow_null=True,
    )
    reason_category = serializers.ChoiceField(
        choices=RejectionCategory.CHOICES,
        required=False,
        write_only=True,
    )
    reason_text = serializers.CharField(
        required=False,
        allow_blank=True,
        write_only=True,
    )
    reviewer_notes = (
        serializers.SerializerMethodField(
            read_only=True,
        )
    )

    def get_reviewer_notes(self, obj):
        audit = (
            obj.rejection_audits.order_by(
                "-rejected_at"
            ).first()
        )
        if audit:
            return audit.reason_text
        return None

    def validate(self, attrs):
        approval = attrs.get("approval_status")
        if (
            approval == ApprovalStatusTypes.REJECTED
            and not attrs.get("reason_category")
        ):
            raise serializers.ValidationError(
                {
                    "reason_category": (
                        "This field is required "
                        "when rejecting."
                    )
                }
            )
        return attrs

    def update(self, instance, validated_data):
        validated_data.pop("reason_category", None)
        validated_data.pop("reason_text", None)
        approval_status = validated_data.get(
            "approval_status",
            instance.approval_status,
        )
        has_plot = hasattr(instance, "plot")
        if approval_status in (
            ApprovalStatusTypes.APPROVED,
            ApprovalStatusTypes.REJECTED,
        ) and has_plot:
            plot = instance.plot
            plot.flagged_for_review = False
            plot.flagged_reason = None
            plot.save(
                update_fields=[
                    "flagged_for_review",
                    "flagged_reason",
                ]
            )
        return super().update(
            instance, validated_data
        )

    class Meta:
        model = Submission
        fields = [
            "approval_status",
            "reason_category",
            "reason_text",
            "reviewer_notes",
        ]


class PlotSerializer(serializers.ModelSerializer):
    submission_uuid = serializers.CharField(
        source="submission.uuid",
        read_only=True,
        allow_null=True,
    )
    form_id = serializers.SlugRelatedField(
        slug_field="asset_uid",
        queryset=FormMetadata.objects.all(),
        source="form",
    )
    approval_status = serializers.IntegerField(
        source="submission.approval_status",
        read_only=True,
        allow_null=True,
    )
    instance_name = (
        serializers.SerializerMethodField()
    )
    plot_name = serializers.SerializerMethodField()
    region = serializers.SerializerMethodField()
    sub_region = serializers.SerializerMethodField()
    enumerator = serializers.SerializerMethodField()

    def get_instance_name(self, obj):
        if obj.submission:
            return obj.submission.instance_name
        return None

    def get_plot_name(self, obj):
        if obj.plot_name:
            return obj.plot_name
        if obj.submission:
            return obj.submission.instance_name
        return None

    def _resolve_plot_fields(self, obj, field_spec):
        """Resolve comma-separated field spec for
        a plot. Builds option_map inline. Non-empty
        resolved values joined with ' - '."""
        option_map, type_map = build_option_lookup(
            obj.form
        )
        raw = obj.submission.raw_data or {}
        fields = [
            f.strip()
            for f in field_spec.split(",")
            if f.strip()
        ]
        parts = []
        for field in fields:
            raw_val = raw.get(field)
            if raw_val is None:
                continue
            opts = option_map.get(field)
            if opts:
                resolved = resolve_value(
                    raw_val,
                    opts,
                    type_map.get(field),
                )
            else:
                resolved = raw_val
            val = str(resolved).strip()
            if val:
                parts.append(val)
        return " - ".join(parts) if parts else None

    def get_region(self, obj):
        field_spec = (
            obj.form.region_field or "region"
        )
        return self._resolve_plot_fields(
            obj, field_spec
        )

    def get_sub_region(self, obj):
        field_spec = (
            obj.form.sub_region_field or "woreda"
        )
        return self._resolve_plot_fields(
            obj, field_spec
        )

    def get_enumerator(self, obj):
        return self._resolve_plot_fields(
            obj, "enumerator_id"
        )

    class Meta:
        model = Plot
        fields = [
            "uuid",
            "plot_name",
            "instance_name",
            "polygon_wkt",
            "min_lat",
            "max_lat",
            "min_lon",
            "max_lon",
            "form_id",
            "region",
            "sub_region",
            "enumerator",
            "created_at",
            "submission_uuid",
            "approval_status",
            "flagged_for_review",
            "flagged_reason",
        ]

        read_only_fields = [
            "uuid",
            "created_at",
            "submission_uuid",
            "approval_status",
            "flagged_for_review",
            "flagged_reason",
        ]


class PlotOverlapQuerySerializer(serializers.Serializer):
    """Input for bounding-box overlap queries."""

    min_lat = CustomFloatField()
    max_lat = CustomFloatField()
    min_lon = CustomFloatField()
    max_lon = CustomFloatField()
    exclude_uuid = CustomCharField(required=False, default="")


class SyncTriggerSerializer(serializers.Serializer):
    """Input for triggering a form sync."""

    asset_uid = CustomCharField()
