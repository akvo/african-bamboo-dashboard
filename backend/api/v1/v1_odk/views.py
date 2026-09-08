import logging
import time
from datetime import datetime, timedelta

from django.conf import settings
from django.db.models import (
    Exists,
    F,
    OuterRef,
    Q,
    Subquery,
)
from django.db.models.fields.json import (
    KeyTextTransform,
)
from django.http import Http404
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django_q.tasks import async_task
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import (
    OpenApiParameter,
    extend_schema,
)
from requests.exceptions import RequestException
from rest_framework import status, viewsets
from rest_framework.exceptions import APIException
from rest_framework.decorators import (
    action,
    api_view,
    permission_classes,
)
from rest_framework.mixins import (
    DestroyModelMixin,
    ListModelMixin,
    RetrieveModelMixin,
    UpdateModelMixin,
)
from rest_framework.permissions import (
    IsAuthenticated,
)
from rest_framework.response import Response
from rest_framework.viewsets import GenericViewSet

from api.v1.v1_init.helpers import get_telegram_config
from api.v1.v1_odk.constants import (
    ApprovalStatusTypes,
    EXCLUDED_QUESTION_TYPES,
    STATUS_MAP,
    ALLOWED_ORDERINGS,
    SyncStatus,
)
from api.v1.v1_odk.funcs import (
    MAPPING_FIELDS,
    check_and_flag_overlaps,
    parse_date_range,
    parse_field_spec,
    rederive_plots,
    strip_id_prefix,
    sync_form_questions,
    validate_and_check_plot,
)
from api.v1.v1_odk.models import (
    FarmerFieldMapping,
    FieldMapping,
    FieldSettings,
    FormMetadata,
    FormOption,
    FormQuestion,
    MainPlotSubmission,
    Plot,
    RejectionAudit,
    Submission,
)
from api.v1.v1_odk.serializers import (
    FieldMappingSerializer,
    FieldSettingsSerializer,
    FormMetadataSerializer,
    SubmissionDetailSerializer,
    SubmissionEditDataSerializer,
    SubmissionListSerializer,
    SubmissionUpdateSerializer,
    SyncTriggerSerializer,
    build_option_lookup,
)
from api.v1.v1_odk.utils.area_calc import (
    calculate_area_ha,
)
from api.v1.v1_odk.utils.farmer_sync import (
    update_farmer_for_submission,
)
from api.v1.v1_odk.utils.plot_id import (
    create_main_plot_for_submission,
)
from api.v1.v1_odk.utils.warning_rules import (
    evaluate_warnings,
)
from utils.encryption import decrypt
from utils.kobo_client import (
    KoboClient,
    KoboUnauthorizedError,
)
from utils.polygon import extract_plot_data

logger = logging.getLogger(__name__)


class AmbiguousSubmission(APIException):
    """Raised when a uuid matches submissions on two forms.

    Only reachable once a cloned Kobo asset has been synced,
    since Kobo reuses _uuid across clones. Answering 409 with
    the remedy beats returning whichever row sorted first.
    """

    status_code = status.HTTP_409_CONFLICT
    # Dict body so callers get a machine-readable error_type,
    # matching kobo_unauthorized and missing_from_kobo.
    default_detail = {
        "detail": (
            "This submission uuid exists on more than one "
            "form. Retry with ?asset_uid=<form> to identify "
            "which."
        ),
        "error_type": "ambiguous_submission",
    }
    default_code = "ambiguous_submission"


def _notification_suffix(audit):
    """Spell out the notification consequence of
    skipping the Kobo sync, for the log."""
    if not audit:
        return ""
    return (
        f", so the Telegram rejection notification "
        f"for audit {audit.pk} will NOT be sent"
    )


def _has_kobo_credentials(user):
    """Check if user has Kobo credentials."""
    return (
        user.kobo_url
        and user.kobo_username
        and user.kobo_password
    )


@extend_schema(tags=["Forms"])
class FormMetadataViewSet(viewsets.ModelViewSet):
    queryset = FormMetadata.objects.all()
    serializer_class = FormMetadataSerializer
    permission_classes = [IsAuthenticated]
    lookup_field = "asset_uid"

    def _make_kobo_client(self, user):
        if not _has_kobo_credentials(user):
            return None
        return KoboClient(
            user.kobo_url,
            user.kobo_username,
            decrypt(user.kobo_password),
        )

    def _try_sync_questions(self, form, user):
        """Fetch form structure from Kobo and
        populate FormQuestion/FormOption.

        Logs and suppresses network errors so the
        caller can proceed without questions.
        """
        client = self._make_kobo_client(user)
        if client is None:
            return
        try:
            content = client.get_asset_detail(
                form.asset_uid
            )
            sync_form_questions(form, content)
        except (
            RequestException,
            KoboUnauthorizedError,
        ):
            logger.warning(
                "Sync questions failed for %s",
                form.asset_uid,
                exc_info=True,
            )

    def perform_create(self, serializer):
        instance = serializer.save()
        self._try_sync_questions(
            instance, self.request.user
        )

    def perform_update(self, serializer):
        form = self.get_object()
        old = {f: getattr(form, f) for f in MAPPING_FIELDS}
        instance = serializer.save()
        changed = any(getattr(instance, f) != old[f] for f in MAPPING_FIELDS)
        if changed:
            rederive_plots(instance)

    @extend_schema(
        tags=["ODK"],
        summary="List available form fields",
        parameters=[
            OpenApiParameter(
                name="is_filter",
                required=False,
                default=False,
                type=OpenApiTypes.BOOL,
                location=OpenApiParameter.QUERY,
            ),
        ],
    )
    @action(detail=True, methods=["get"])
    def form_fields(self, request, asset_uid=None):
        """List locally-stored form questions.

        If no questions exist yet, attempts a
        one-time fetch from KoboToolbox.
        """
        form = self.get_object()

        if not FormQuestion.objects.filter(
            form=form
        ).exists():
            self._try_sync_questions(
                form, request.user
            )

        qs = FormQuestion.objects.filter(form=form).order_by("pk")

        if request.query_params.get("is_filter") == "true":
            excluded = set()
            for spec in [
                form.region_field,
                form.sub_region_field,
                form.plot_name_field,
            ]:
                if spec:
                    for f in spec.split(","):
                        s = f.strip()
                        if s:
                            excluded.add(s)
            if excluded:
                qs = qs.exclude(name__in=excluded)

        fields = [
            {
                "name": q.name,
                "type": q.type,
                "label": q.label,
                "full_path": q.name,
            }
            for q in qs
        ]
        return Response({"fields": fields})

    @extend_schema(
        tags=["ODK"],
        summary="List local form questions with IDs",
    )
    @action(detail=True, methods=["get"])
    def form_questions(self, request, asset_uid=None):
        """Return FormQuestion records stored in DB
        for a given form, including their IDs."""
        form = self.get_object()
        qs = (
            FormQuestion.objects.filter(form=form)
            .prefetch_related("options")
            .order_by("pk")
        )
        data = []
        for q in qs:
            item = {
                "id": q.pk,
                "name": q.name,
                "label": q.label,
                "type": q.type,
            }
            if q.type.startswith("select_"):
                item["options"] = [
                    {
                        "name": o.name,
                        "label": o.label,
                    }
                    for o in q.options.all()
                ]
            data.append(item)
        return Response(data)

    @extend_schema(
        tags=["Forms"],
        summary=("Get or update farmer field mapping"),
    )
    @action(
        detail=True,
        methods=["get", "put"],
        url_path="farmer-field-mapping",
    )
    def farmer_field_mapping(self, request, asset_uid=None):
        """GET: return current mapping.
        PUT: create or update mapping."""
        form = self.get_object()
        if request.method == "GET":
            mapping = (
                FarmerFieldMapping.objects
                .filter(form=form)
                .first()
            )
            if not mapping:
                return Response(
                    {
                        "unique_fields": [],
                        "values_fields": [],
                        "uid_start": 1,
                    }
                )
            return Response(
                self._serialize_farmer_mapping(
                    mapping
                )
            )

        # PUT
        raw_unique = request.data.get(
            "unique_fields", []
        )
        raw_values = request.data.get(
            "values_fields", []
        )

        for name, val in [
            ("unique_fields", raw_unique),
            ("values_fields", raw_values),
        ]:
            if not isinstance(val, list):
                return Response(
                    {
                        "detail": (
                            f"{name} must be a list"
                        )
                    },
                    status=(
                        status.HTTP_400_BAD_REQUEST
                    ),
                )

        # Strip and deduplicate
        unique = list(
            dict.fromkeys(
                s.strip()
                for s in raw_unique
                if isinstance(s, str)
                and s.strip()
            )
        )
        values = list(
            dict.fromkeys(
                s.strip()
                for s in raw_values
                if isinstance(s, str)
                and s.strip()
            )
        )

        if not unique:
            return Response(
                {
                    "detail": (
                        "unique_fields is required"
                    )
                },
                status=(
                    status.HTTP_400_BAD_REQUEST
                ),
            )

        unique_str = ",".join(unique)
        values_str = ",".join(values)

        # Validate uid_start (optional)
        raw_uid_start = request.data.get(
            "uid_start", None
        )
        uid_start = 1
        if raw_uid_start is not None:
            try:
                uid_start = int(raw_uid_start)
                if uid_start < 1:
                    raise ValueError
            except (TypeError, ValueError):
                return Response(
                    {
                        "detail": (
                            "uid_start must be a "
                            "positive integer"
                        )
                    },
                    status=(
                        status.HTTP_400_BAD_REQUEST
                    ),
                )

        mapping, _ = (
            FarmerFieldMapping.objects
            .update_or_create(
                form=form,
                defaults={
                    "unique_fields": unique_str,
                    "values_fields": (
                        values_str or unique_str
                    ),
                    "uid_start": uid_start,
                },
            )
        )
        return Response(
            self._serialize_farmer_mapping(
                mapping
            )
        )

    @staticmethod
    def _serialize_farmer_mapping(mapping):
        """Serialize a FarmerFieldMapping to dict."""
        return {
            "unique_fields": parse_field_spec(
                mapping.unique_fields
            ),
            "values_fields": parse_field_spec(
                mapping.values_fields
            ),
            "uid_start": mapping.uid_start,
        }

    @extend_schema(
        request=SyncTriggerSerializer,
        tags=["ODK"],
        summary="Trigger sync from KoboToolbox",
    )
    @action(detail=True, methods=["post"])
    def sync(self, request, asset_uid=None):
        """Fetch submissions from KoboToolbox
        and upsert into local DB."""
        form = self.get_object()
        client = self._make_kobo_client(request.user)
        if client is None:
            return Response(
                {"message": "No Kobo credentials"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Sync form questions and options
        questions_synced = 0
        try:
            content = client.get_asset_detail(form.asset_uid)
            questions_synced = sync_form_questions(form, content)
        except KoboUnauthorizedError:
            return Response(
                {
                    "message": (
                        "KoboToolbox credentials are "
                        "invalid or expired. Please "
                        "log in again."
                    ),
                    "error_type": "kobo_unauthorized",
                },
                status=status.HTTP_403_FORBIDDEN,
            )
        except Exception as e:
            return Response(
                {"message": (f"Error syncing form " f"questions: {str(e)}")},
                status=status.HTTP_502_BAD_GATEWAY,
            )

        # Always fetch ALL submissions — Kobo does
        # not expose a per-submission modified
        # timestamp, so incremental sync by
        # _submission_time misses edits and
        # validation-status changes.
        try:
            results = (
                client.fetch_all_submissions(
                    form.asset_uid
                )
            )
        except KoboUnauthorizedError:
            return Response(
                {
                    "message": (
                        "KoboToolbox credentials are "
                        "invalid or expired. Please "
                        "log in again."
                    ),
                    "error_type": "kobo_unauthorized",
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        counts = {
            "created": 0,
            "updated": 0,
            "plots_created": 0,
            "plots_updated": 0,
            "plots_flagged": 0,
        }

        for item in results:
            sub, is_new = self._upsert_submission(
                form, item
            )
            if is_new:
                counts["created"] += 1
            else:
                counts["updated"] += 1
            self._upsert_plot(
                form, sub, item, counts
            )
            self._queue_attachment_download(
                request.user, item, sub
            )

        if results:
            latest = max(
                r["_submission_time"]
                for r in results
            )
            form.last_sync_timestamp = int(
                datetime.fromisoformat(
                    latest
                ).timestamp()
                * 1000
            )
            form.save()

        # Reporting stale rows must never break the sync
        # itself. This path is new and runs against forms far
        # larger than any test fixture, so a failure here
        # degrades to "no stale count" rather than a 500 on an
        # operation that otherwise succeeded.
        try:
            counts["stale"] = (
                self._flag_stale_submissions(form, results)
            )
            deleted, kept = self._delete_stale_submissions(
                form
            )
            counts["stale_deleted"] = deleted
            counts["stale_kept"] = kept
        except Exception:
            counts["stale"] = 0
            counts["stale_deleted"] = 0
            counts["stale_kept"] = 0
            logger.exception(
                "Stale-submission check failed for form %s "
                "— the sync itself succeeded",
                form.asset_uid,
            )

        # Post-sync sweep: re-check plots whose
        # flags were cleared by old buggy code
        unchecked = Plot.objects.filter(
            form=form,
            flagged_for_review__isnull=True,
            polygon_wkt__isnull=False,
        )
        for plot in unchecked.iterator():
            check_and_flag_overlaps(plot)
            if plot.flagged_for_review:
                counts["plots_flagged"] += 1

        # Sync farmer records asynchronously
        async_task(
            "api.v1.v1_odk.utils.farmer_sync"
            ".sync_farmers_for_form",
            form,
        )

        return Response(
            {
                "synced": len(results),
                "questions_synced": (
                    questions_synced
                ),
                **counts,
            }
        )

    def _flag_stale_submissions(self, form, results):
        """Mark local rows KoboToolbox no longer returns.

        A submission deleted in Kobo leaves a local row that
        can never sync again: every validation-status update
        for it answers 400 "One or more submission ids are
        invalid", so a rejection on it silently never reaches
        Kobo and never notifies anyone.

        Flagged, never deleted here — the row may carry a
        Plot, rejection history and a Plot ID link, so removal
        is an explicit operator action. Skipped entirely on an
        empty result, since a failed or partial fetch must not
        condemn every row.

        The set difference is computed in Python rather than
        with `kobo_id__in=<every fetched id>`. That clause
        binds one parameter per submission against Postgres's
        65,535 limit, and it would run twice per sync on a
        form of any size.

        Returns the number of rows currently flagged.
        """
        if not results:
            return 0

        fetched_ids = {
            str(r["_id"]) for r in results if r.get("_id")
        }
        if not fetched_ids:
            return 0

        local = Submission.objects.filter(form=form)
        local_ids = set(
            local.values_list("kobo_id", flat=True)
        )
        flagged_ids = set(
            local.filter(
                missing_from_kobo_at__isnull=False
            ).values_list("kobo_id", flat=True)
        )

        # Anything that reappeared is no longer stale. Scoped
        # to rows already flagged, which is a small set.
        reappeared = flagged_ids & fetched_ids
        if reappeared:
            local.filter(kobo_id__in=reappeared).update(
                missing_from_kobo_at=None
            )

        stale_ids = local_ids - fetched_ids
        newly_stale = sorted(stale_ids - flagged_ids)
        if newly_stale:
            local.filter(kobo_id__in=newly_stale).update(
                missing_from_kobo_at=timezone.now()
            )
            logger.warning(
                "%s submission(s) on form %s are no longer "
                "in KoboToolbox (ids: %s). Approve/reject is "
                "now blocked for them, because the update "
                "cannot reach Kobo and no Telegram "
                "notification would be sent.",
                len(newly_stale),
                form.asset_uid,
                ", ".join(newly_stale[:20]),
            )
        return len(stale_ids)

    def _delete_stale_submissions(self, form):
        """Remove rows KoboToolbox has not returned for a
        while, when the deployment has opted in.

        Off unless SYNC_DELETE_STALE_AFTER_DAYS is positive.
        Flagging is reversible and deleting is not, so the
        default is to flag and let an operator decide.

        Three guards, because this runs unattended:

        1. A grace period. The row must have been flagged for
           the configured number of days, so a Kobo outage
           that resolves on the next sync cannot take data
           with it -- _flag_stale_submissions clears the flag
           the moment a submission reappears.
        2. Rows carrying user-visible history are kept. A
           rejection audit or a Plot ID is a record someone
           made, not Kobo data, and it should not disappear
           because an upstream row did. Deleting those stays
           a deliberate act through the UI.
        3. The plot goes with the submission, since
           Plot.submission is SET_NULL and an orphaned plot
           has no data and no possible action.

        Returns (deleted, kept).
        """
        days = getattr(
            settings, "SYNC_DELETE_STALE_AFTER_DAYS", 0
        )
        if days <= 0:
            return 0, 0

        cutoff = timezone.now() - timedelta(days=days)
        due = Submission.objects.filter(
            form=form,
            missing_from_kobo_at__isnull=False,
            missing_from_kobo_at__lt=cutoff,
        )

        protected = set(
            due.filter(
                Q(rejection_audits__isnull=False)
                | Q(main_plot_submission__isnull=False)
            ).values_list("pk", flat=True)
        )
        removable = {
            pk: uuid
            for pk, uuid in due.values_list("pk", "uuid")
            if pk not in protected
        }

        kept = len(protected)
        deleted = len(removable)
        if deleted:
            Plot.objects.filter(
                submission_id__in=removable
            ).delete()
            Submission.objects.filter(
                pk__in=removable
            ).delete()
            uuids = list(removable.values())[:20]
            logger.warning(
                "Deleted %s submission(s) and their plots "
                "on form %s, absent from KoboToolbox for "
                "more than %s day(s) (uuids: %s)",
                deleted,
                form.asset_uid,
                days,
                ", ".join(uuids),
            )
        if kept:
            logger.info(
                "Kept %s stale submission(s) on form %s "
                "that carry a rejection audit or Plot ID; "
                "delete those from the plot detail panel.",
                kept,
                form.asset_uid,
            )
        return deleted, kept

    def _upsert_submission(self, form, item):
        """Upsert a single Kobo submission."""
        sub_time_str = item.get(
            "_submission_time", ""
        )
        sub_time_ms = int(
            datetime.fromisoformat(
                sub_time_str
            ).timestamp()
            * 1000
        )
        vs = item.get(
            "_validation_status", {}
        )
        kobo_uid = (
            vs.get("uid") if vs else None
        )
        approval = (
            ApprovalStatusTypes
            .ReverseKoboStatusMap
            .get(kobo_uid)
            if kobo_uid
            else None
        )
        # Keyed on (form, kobo_id). Neither Kobo field is
        # stable on its own:
        #
        #   edit in Kobo -> _id stays, _uuid CHANGES
        #   re-import    -> _id changes, _uuid stays
        #
        # _id is Kobo's own operational identifier -- it is
        # what /data/<id> and update_validation_statuses use
        # -- and editing is by far the common case, so _id is
        # the key and uuid is refreshed as data.
        #
        # On a re-import the old _id disappears from Kobo, so
        # the superseded row is picked up by the stale sweep
        # rather than being silently carried forward.
        return Submission.objects.update_or_create(
            form=form,
            kobo_id=str(item["_id"]),
            defaults={
                "uuid": item["_uuid"],
                "submission_time": sub_time_ms,
                "submitted_by": item.get(
                    "_submitted_by"
                ),
                "instance_name": item.get(
                    "meta/instanceName"
                ),
                "approval_status": approval,
                "raw_data": item,
                "system_data": {
                    "_geolocation": item.get(
                        "_geolocation"
                    ),
                    "_tags": item.get(
                        "_tags", []
                    ),
                },
            },
        )

    def _upsert_plot(self, form, sub, item, counts):
        """Create/update plot from submission data
        with geometry validation and overlap check."""
        plot_data = extract_plot_data(item, form)
        raw_polygon = plot_data.get(
            "raw_polygon_string"
        )
        area = calculate_area_ha(raw_polygon)

        # Run warning rules for valid geometry
        warnings = []
        if plot_data["polygon_wkt"]:
            warnings = evaluate_warnings(
                raw_polygon, area
            )

        # Merge geometry errors + warnings
        all_flags = []
        if plot_data["flagged_reason"]:
            all_flags.extend(
                plot_data["flagged_reason"]
            )
        if warnings:
            all_flags.extend(warnings)

        defaults = {
            "form": form,
            "plot_name": plot_data["plot_name"],
            "polygon_source_field": plot_data[
                "polygon_source_field"
            ],
            "polygon_wkt": plot_data[
                "polygon_wkt"
            ],
            "min_lat": plot_data["min_lat"],
            "max_lat": plot_data["max_lat"],
            "min_lon": plot_data["min_lon"],
            "max_lon": plot_data["max_lon"],
            "region": plot_data["region"],
            "sub_region": plot_data["sub_region"],
            "area_ha": area,
        }
        if all_flags:
            defaults["flagged_for_review"] = True
            defaults["flagged_reason"] = all_flags
        elif plot_data["flagged_for_review"]:
            defaults["flagged_for_review"] = True
            defaults["flagged_reason"] = (
                plot_data["flagged_reason"]
            )

        # Preserve created_at on re-sync: fetch
        # existing value before update_or_create
        # overwrites it.  Django 4.2 lacks
        # create_defaults so we include created_at
        # in defaults for both paths.
        existing = Plot.objects.filter(
            submission=sub
        ).values_list(
            "created_at", flat=True
        ).first()
        defaults["created_at"] = (
            existing
            if existing is not None
            else int(time.time() * 1000)
        )

        plot, plot_is_new = (
            Plot.objects.update_or_create(
                submission=sub,
                defaults=defaults,
            )
        )
        if plot_is_new:
            counts["plots_created"] += 1
        else:
            counts["plots_updated"] += 1

        if plot_data["polygon_wkt"]:
            check_and_flag_overlaps(plot)
        if plot.flagged_for_review:
            counts["plots_flagged"] += 1

    def _queue_attachment_download(
        self, user, item, sub
    ):
        """Queue async download of image
        attachments from Kobo."""
        has_images = any(
            a.get("mimetype", "").startswith(
                "image/"
            )
            for a in item.get(
                "_attachments", []
            )
        )
        if has_images:
            async_task(
                "api.v1.v1_odk.tasks"
                ".download_submission"
                "_attachments",
                user.kobo_url,
                user.kobo_username,
                user.kobo_password,
                str(sub.uuid),
                sub.form.asset_uid,
            )


@extend_schema(tags=["Submissions"])
class SubmissionViewSet(
    ListModelMixin,
    RetrieveModelMixin,
    UpdateModelMixin,
    DestroyModelMixin,
    GenericViewSet,
):
    queryset = Submission.objects.all()
    permission_classes = [IsAuthenticated]
    lookup_field = "uuid"

    def get_object(self):
        """Resolve a submission by uuid, per form.

        Kobo reuses _uuid across cloned assets, so uuid is
        unique per form rather than globally. A bare
        /submissions/<uuid>/ can therefore match more than one
        row once a cloned form has been synced.

        Rather than silently picking one — which would show
        the wrong form's data, or apply a decision to it —
        narrow by ?asset_uid= when given and refuse loudly
        when the uuid is still ambiguous.
        """
        qs = self.filter_queryset(self.get_queryset())
        qs = qs.filter(uuid=self.kwargs["uuid"])

        asset_uid = self.request.query_params.get("asset_uid")
        if asset_uid:
            qs = qs.filter(form__asset_uid=asset_uid)

        matches = list(qs[:2])
        if not matches:
            raise Http404(
                "No submission matches the given uuid."
            )

        if len(matches) > 1:
            if len({m.form_id for m in matches}) > 1:
                # Different assets: unrelated submissions
                # that merely share an instance uuid.
                # Returning either would show the wrong
                # form's data, or apply a validator's
                # decision to it.
                raise AmbiguousSubmission()
            # Same asset: a re-import kept the uuid under a
            # new _id, so the old row is superseded and about
            # to be flagged stale. Meta.ordering is
            # -submission_time, so matches[0] is the current
            # one.
            logger.info(
                "uuid %s matches %s rows on form %s; using "
                "the most recent (kobo_id=%s). The others "
                "were superseded by a re-import.",
                self.kwargs["uuid"],
                len(matches),
                matches[0].form_id,
                matches[0].kobo_id,
            )

        self.check_object_permissions(self.request, matches[0])
        return matches[0]

    def get_serializer_class(self):
        if self.action == "retrieve":
            return SubmissionDetailSerializer
        if self.action in (
            "update",
            "partial_update",
        ):
            return SubmissionUpdateSerializer
        return SubmissionListSerializer

    def _get_form_by_uid(self, asset_uid):
        """Fetch FormMetadata by asset_uid,
        return None if not found."""
        try:
            return FormMetadata.objects.get(
                asset_uid=asset_uid
            )
        except FormMetadata.DoesNotExist:
            return None

    def get_serializer_context(self):
        ctx = super().get_serializer_context()
        if self.action == "list":
            asset_uid = (
                self.request.query_params.get(
                    "asset_uid"
                )
            )
            form = (
                self._get_form_by_uid(asset_uid)
                if asset_uid
                else None
            )
            if form:
                om, tm = build_option_lookup(form)
                ctx["option_lookup"] = om
                ctx["type_map"] = tm
                ctx["question_names"] = {
                    q["name"]
                    for q in (
                        self._get_form_questions(
                            form
                        )
                    )
                }
        return ctx

    def _get_form_questions(self, form):
        """Return displayable form questions,
        excluding mapped and system fields."""
        mapped_fields = set()
        for spec in [
            form.region_field,
            form.sub_region_field,
        ]:
            mapped_fields.update(
                parse_field_spec(spec)
            )
        qs = (
            FormQuestion.objects.filter(form=form)
            .exclude(
                Q(
                    type__in=(
                        EXCLUDED_QUESTION_TYPES
                    )
                )
                | Q(name__startswith="validate_")
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

    def list(self, request, *args, **kwargs):
        response = super().list(
            request, *args, **kwargs
        )
        asset_uid = request.query_params.get(
            "asset_uid"
        )
        form = (
            self._get_form_by_uid(asset_uid)
            if asset_uid
            else None
        )
        if form:
            response.data["questions"] = (
                self._get_form_questions(form)
            )
            response.data["sortable_fields"] = (
                form.sortable_fields or []
            )
        else:
            response.data["questions"] = []
            response.data["sortable_fields"] = []
        return response

    def get_queryset(self):
        qs = super().get_queryset().prefetch_related(
            "main_plot_submission__main_plot"
        )
        params = self.request.query_params
        asset_uid = params.get("asset_uid")
        if asset_uid:
            qs = qs.filter(form__asset_uid=asset_uid)
        status_param = params.get("status")
        if status_param is not None:
            if status_param == "pending":
                qs = qs.filter(approval_status__isnull=True)
            elif status_param in STATUS_MAP:
                qs = qs.filter(approval_status=(STATUS_MAP[status_param]))
        region = params.get("region")
        if region:
            qs = qs.filter(plot__region=region)
        sub_region = params.get("sub_region")
        if sub_region:
            qs = qs.filter(plot__sub_region=sub_region)
        search = params.get("search")
        if search:
            stripped = strip_id_prefix(search)
            plot_uid_match = Exists(
                MainPlotSubmission.objects.filter(
                    submission=OuterRef("pk"),
                    main_plot__uid__icontains=(
                        stripped
                    ),
                )
            )
            qs = qs.filter(
                Q(
                    instance_name__icontains=search
                )
                | Q(kobo_id__icontains=stripped)
                | Q(plot_uid_match)
            )
        start_date, end_date = parse_date_range(params)
        if start_date is not None:
            qs = qs.filter(submission_time__gte=start_date)
        if end_date is not None:
            qs = qs.filter(submission_time__lte=end_date)
        # Dynamic raw_data filters
        if asset_uid:
            qs = self._apply_dynamic_filters(qs, params, asset_uid)
        # Sorting
        qs = qs.annotate(
            sort_start=KeyTextTransform(
                "start", "raw_data"
            ),
            sort_end=KeyTextTransform(
                "end", "raw_data"
            ),
            sort_main_plot_uid=Subquery(
                MainPlotSubmission.objects.filter(
                    submission=OuterRef("pk"),
                ).values("main_plot__uid")[:1]
            ),
        )
        ordering = params.get("ordering")
        if ordering:
            desc = ordering.startswith("-")
            field = ordering.lstrip("-")
            orm_field = ALLOWED_ORDERINGS.get(field)
            if orm_field:
                expr = F(orm_field)
                if desc:
                    expr = expr.desc(nulls_last=True)
                else:
                    expr = expr.asc(nulls_last=True)
                qs = qs.order_by(
                    expr,
                    "-submission_time",
                    "pk",
                )
            elif asset_uid:
                qs = self._apply_dynamic_ordering(qs, asset_uid, field, desc)
        return qs

    def _apply_dynamic_ordering(self, qs, asset_uid, field, desc):
        try:
            form = FormMetadata.objects.get(asset_uid=asset_uid)
        except FormMetadata.DoesNotExist:
            return qs
        allowed = form.sortable_fields or []
        if field not in allowed:
            return qs
        ann_key = f"sort_dyn_{field}"
        qs = qs.annotate(**{ann_key: KeyTextTransform(field, "raw_data")})
        sort_key = ann_key
        # For select_one fields, sort by resolved
        # option label instead of raw option name
        question = FormQuestion.objects.filter(
            form=form,
            name=field,
            type="select_one",
        ).first()
        if question:
            label_key = f"sort_label_{field}"
            qs = qs.annotate(
                **{
                    label_key: Subquery(
                        FormOption.objects.filter(
                            question=question,
                            name=OuterRef(ann_key),
                        ).values("label")[:1]
                    )
                }
            )
            sort_key = label_key
        expr = F(sort_key)
        if desc:
            expr = expr.desc(nulls_last=True)
        else:
            expr = expr.asc(nulls_last=True)
        return qs.order_by(expr, "-submission_time", "pk")

    def _apply_dynamic_filters(self, qs, params, asset_uid):
        filter_keys = [k for k in params if k.startswith("filter__")]
        if not filter_keys:
            return qs
        try:
            form = FormMetadata.objects.get(asset_uid=asset_uid)
        except FormMetadata.DoesNotExist:
            return qs
        allowed = form.filter_fields or []
        for key in filter_keys:
            field_name = \
                key[len("filter__"):]
            if field_name in allowed:
                qs = qs.filter(**{f"raw_data__{field_name}": (params[key])})
        return qs

    def update(self, request, *args, **kwargs):
        """Refuse approve/reject on a stale submission.

        Covers PATCH too (partial_update delegates here).
        The UI disables these actions, but a stale row
        must be refused server-side as well: letting it
        through writes a local decision that can never
        reach Kobo and never notifies the field team.
        """
        instance = self.get_object()
        if instance.missing_from_kobo_at:
            return Response(
                {
                    "detail": (
                        "This submission no longer "
                        "exists in KoboToolbox, so the "
                        "decision cannot be synced and "
                        "the field team cannot be "
                        "notified. Delete it instead."
                    ),
                    "error_type": "missing_from_kobo",
                },
                status=status.HTTP_409_CONFLICT,
            )
        return super().update(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        """Delete a submission Kobo no longer has.

        Authorization is deliberately IsAuthenticated, the
        same bar as approve/reject on this viewset. Accounts
        are provisioned from KoboToolbox and created with
        is_superuser=False, so a superuser gate would make
        this unusable for every real operator rather than
        making it safer.

        What bounds the damage instead is the object-level
        check below: only a submission KoboToolbox no longer
        has can be deleted. Its rejection history and Plot
        ID link describe a submission that is already gone
        upstream, so this is cleanup, not destruction of
        live data. A live submission is refused outright —
        Kobo would restore it on the next sync anyway.
        """
        instance = self.get_object()
        if not instance.missing_from_kobo_at:
            return Response(
                {
                    "detail": (
                        "Only a submission missing from "
                        "KoboToolbox can be deleted "
                        "here."
                    )
                },
                status=status.HTTP_409_CONFLICT,
            )
        # Plot.submission is SET_NULL, so the plot would
        # otherwise outlive the submission as an orphan: no
        # data, no possible action, and every field resolved
        # from raw_data unavailable. Remove it in the same
        # operation rather than leaving a ghost on the map.
        plot = getattr(instance, "plot", None)
        plot_uuid = plot.uuid if plot else None

        logger.warning(
            "User %s deleted submission %s (kobo_id=%s) and "
            "its plot %s, which KoboToolbox no longer has. "
            "Rejection history and the Plot ID link go with "
            "them.",
            request.user.pk,
            instance.uuid,
            instance.kobo_id,
            plot_uuid or "(none)",
        )
        if plot:
            plot.delete()
        return super().destroy(request, *args, **kwargs)

    def perform_update(self, serializer):
        reason_category = serializer.validated_data.get("reason_category")
        reason_text = serializer.validated_data.get("reason_text", "")
        instance = serializer.save(
            updated_by=self.request.user,
            updated_at=timezone.now(),
        )
        approval = instance.approval_status

        # Generate Plot ID on first approval
        # (kept permanently — never unlinked on revert/reject)
        if approval == ApprovalStatusTypes.APPROVED:
            create_main_plot_for_submission(instance)

        # Re-check polygon & overlaps on revert
        if approval is None:
            plot = getattr(instance, "plot", None)
            if plot:
                validate_and_check_plot(plot)

        # Create RejectionAudit for rejections
        audit = None
        if approval == ApprovalStatusTypes.REJECTED:
            plot = getattr(instance, "plot", None)
            if not reason_category:
                # No audit row means no notification
                # and no rejection history, while the
                # caller still gets 200. Say so.
                logger.warning(
                    "Submission %s rejected without a "
                    "reason_category — no "
                    "RejectionAudit created, so no "
                    "Telegram notification is sent",
                    instance.uuid,
                )
            elif not plot:
                logger.warning(
                    "Submission %s rejected but has "
                    "no linked Plot — no "
                    "RejectionAudit created, so no "
                    "Telegram notification is sent",
                    instance.uuid,
                )
            else:
                audit = RejectionAudit.objects.create(
                    plot=plot,
                    submission=instance,
                    validator=(self.request.user),
                    reason_category=(reason_category),
                    reason_text=reason_text,
                )

        kobo_key = approval \
            if approval is not None else ApprovalStatusTypes.PENDING
        kobo_uid = ApprovalStatusTypes.KoboStatusMap.get(kobo_key)
        if not kobo_uid:
            logger.warning(
                "No Kobo status mapping for "
                "approval_status=%s on submission "
                "%s — skipping Kobo sync%s",
                kobo_key,
                instance.uuid,
                _notification_suffix(audit),
            )
            return
        user = self.request.user
        if not _has_kobo_credentials(user):
            logger.warning(
                "User %s has no KoboToolbox "
                "credentials (url/username/password) "
                "— skipping Kobo sync for submission "
                "%s%s",
                user.pk,
                instance.uuid,
                _notification_suffix(audit),
            )
            return

        task_kwargs = {}
        if audit:
            task_kwargs["hook"] = "api.v1.v1_odk.tasks"\
                ".on_kobo_sync_complete"
            task_kwargs["audit_id"] = audit.pk

        async_task(
            "api.v1.v1_odk.tasks" ".sync_kobo_validation_status",
            user.kobo_url,
            user.kobo_username,
            user.kobo_password,
            instance.form.asset_uid,
            [instance.kobo_id],
            kobo_key,
            **task_kwargs,
        )

    @extend_schema(
        tags=["Submissions"],
        summary="Edit submission field data",
        request=SubmissionEditDataSerializer,
    )
    @action(
        detail=True,
        methods=["patch"],
        url_path="edit_data",
    )
    def edit_data(self, request, uuid=None):
        """Edit submission raw_data fields and
        sync changes to KoboToolbox."""
        submission = self.get_object()
        serializer = SubmissionEditDataSerializer(
            data=request.data,
            context={
                "submission": submission,
                "request": request,
            },
        )
        serializer.is_valid(raise_exception=True)
        fields = (
            serializer.validated_data["fields"]
        )

        raw = submission.raw_data or {}
        raw.update(fields)
        submission.raw_data = raw
        submission.updated_by = request.user
        submission.updated_at = timezone.now()
        submission.save(
            update_fields=[
                "raw_data",
                "updated_by",
                "updated_at",
            ]
        )

        plot = getattr(submission, "plot", None)
        if plot:
            self._update_plot_from_edit(
                plot, submission, fields
            )

        self._resync_farmers_if_needed(
            submission, fields
        )

        self._sync_edit_to_kobo(
            request.user, submission, fields
        )

        detail_serializer = (
            SubmissionDetailSerializer(submission)
        )
        return Response(detail_serializer.data)

    def _update_plot_from_edit(
        self, plot, submission, fields
    ):
        """Update Plot.region/sub_region/plot_name
        if corresponding raw_data fields changed."""
        form = submission.form
        raw = submission.raw_data or {}

        # (plot_attr, form_spec, joiner, empty)
        field_map = [
            (
                "region",
                form.region_field,
                " - ",
                "",
            ),
            (
                "sub_region",
                form.sub_region_field,
                " - ",
                "",
            ),
            (
                "plot_name",
                form.plot_name_field,
                " ",
                None,
            ),
        ]

        update_fields = []
        for attr, spec, sep, empty in field_map:
            names = parse_field_spec(spec)
            if not any(f in fields for f in names):
                continue
            vals = [
                str(raw.get(f, ""))
                for f in names
                if raw.get(f)
            ]
            setattr(
                plot,
                attr,
                sep.join(vals) if vals else empty,
            )
            update_fields.append(attr)

        if update_fields:
            plot.save(
                update_fields=update_fields
            )

    def _resync_farmers_if_needed(
        self, submission, fields
    ):
        """Update farmer record if any
        farmer-related fields were edited.

        Uses targeted update_farmer_for_submission
        instead of full sync_farmers_for_form to
        preserve the existing Plot.farmer
        relationship and avoid generating new
        farmer UIDs on name changes."""
        form = submission.form
        farmer_mapping = (
            form.farmer_field_mapping.first()
        )
        if not farmer_mapping:
            return
        all_farmer_q_names = set(
            parse_field_spec(
                farmer_mapping.unique_fields
            )
            + parse_field_spec(
                farmer_mapping.values_fields
            )
        )
        if all_farmer_q_names & set(fields.keys()):
            update_farmer_for_submission(
                form, submission
            )

    def _sync_edit_to_kobo(
        self, user, submission, fields
    ):
        """Queue async task to push field edits
        to KoboToolbox."""
        if not _has_kobo_credentials(user):
            return
        async_task(
            "api.v1.v1_odk.tasks"
            ".sync_kobo_submission_data",
            user.kobo_url,
            user.kobo_username,
            user.kobo_password,
            submission.form.asset_uid,
            submission.kobo_id,
            fields,
        )

    @extend_schema(tags=["ODK"])
    @action(detail=False, methods=["get"])
    def latest_sync_time(self, request):
        """Get latest submission_time
        for a form."""
        asset_uid = request.query_params.get("asset_uid")
        if not asset_uid:
            return Response(
                {"message": ("asset_uid is required")},
                status=status.HTTP_400_BAD_REQUEST,
            )
        latest = (
            Submission.objects.filter(form__asset_uid=asset_uid)
            .order_by("-submission_time")
            .values_list("submission_time", flat=True)
            .first()
        )
        return Response({"latest_submission_time": latest})


@extend_schema(tags=["Field Settings"])
class FieldSettingsViewSet(
    ListModelMixin,
    GenericViewSet,
):
    """Read-only list of standardized fields."""

    queryset = FieldSettings.objects.all().order_by("pk")
    serializer_class = FieldSettingsSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = None


@extend_schema(tags=["Field Mappings"])
class FieldMappingViewSet(
    ListModelMixin,
    GenericViewSet,
):
    """List and bulk-upsert field mappings."""

    queryset = FieldMapping.objects.all()
    serializer_class = FieldMappingSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = None

    def get_queryset(self):
        qs = super().get_queryset()
        form_id = self.request.query_params.get("form_id")
        if form_id:
            qs = qs.filter(form__asset_uid=form_id)
        return qs.select_related("field", "form_question")

    @extend_schema(
        summary="Bulk upsert field mappings",
    )
    @action(
        detail=False,
        methods=["put"],
        url_path=r"(?P<asset_uid>[^/.]+)",
    )
    def bulk_upsert(self, request, asset_uid=None):
        """Bulk upsert mappings for a form.

        Body: { "field_name": question_id, ... }
        Set question_id to null to delete.
        """
        try:
            form = FormMetadata.objects.get(asset_uid=asset_uid)
        except FormMetadata.DoesNotExist:
            return Response(
                {"detail": "Form not found"},
                status=status.HTTP_404_NOT_FOUND,
            )

        data = request.data
        if not isinstance(data, dict):
            return Response(
                {"detail": ("Expected a JSON object")},
                status=(status.HTTP_400_BAD_REQUEST),
            )

        errors = {}
        for field_name, q_id in data.items():
            try:
                field_setting = FieldSettings.objects.get(name=field_name)
            except FieldSettings.DoesNotExist:
                errors[field_name] = "Unknown field setting"
                continue

            if q_id is None:
                FieldMapping.objects.filter(
                    field=field_setting,
                    form=form,
                ).delete()
                continue

            try:
                question = FormQuestion.objects.get(pk=q_id, form=form)
            except FormQuestion.DoesNotExist:
                errors[field_name] = f"Question {q_id} not found"
                continue

            FieldMapping.objects.update_or_create(
                field=field_setting,
                form=form,
                defaults={
                    "form_question": question,
                },
            )

        if errors:
            return Response(
                {"errors": errors},
                status=(status.HTTP_400_BAD_REQUEST),
            )

        mappings = FieldMapping.objects.filter(form=form).select_related(
            "field", "form_question"
        )
        return Response(FieldMappingSerializer(mappings, many=True).data)


@extend_schema(
    description=(
        "Re-queue the Telegram rejection notification "
        "for an audit that never fully delivered. "
        "Superuser only."
    ),
    request=None,
    responses=OpenApiTypes.OBJECT,
    tags=["Submissions"],
)
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def resend_rejection_notification(request, pk):
    """Re-queue delivery for one RejectionAudit.

    IsAuthenticated, matching approve/reject: accounts are
    provisioned from KoboToolbox with is_superuser=False, so
    a superuser gate would leave nobody able to use this.

    Safe to call twice: the task skips any chat already in
    the delivery ledger, so a partially delivered audit
    never double-posts. The 409s below are what keep it
    from sending something it should not.
    """
    audit = get_object_or_404(RejectionAudit, pk=pk)

    tg_config = get_telegram_config()
    if (
        not tg_config["enabled"]
        or not tg_config["bot_token"]
    ):
        return Response(
            {
                "detail": (
                    "Telegram notifications are "
                    "disabled or not configured."
                )
            },
            status=status.HTTP_409_CONFLICT,
        )

    if audit.sync_status != SyncStatus.SYNCED:
        return Response(
            {
                "detail": (
                    "This rejection never reached "
                    "KoboToolbox, so no notification "
                    "may be sent for it."
                )
            },
            status=status.HTTP_409_CONFLICT,
        )

    if audit.telegram_sent_at:
        return Response(
            {
                "detail": (
                    "This notification was already "
                    "delivered to every configured "
                    "group."
                )
            },
            status=status.HTTP_409_CONFLICT,
        )

    # Zeroing the counter also re-arms the retry sweep,
    # so one click restores automatic recovery instead
    # of being a one-shot.
    audit.telegram_attempts = 0
    audit.save(update_fields=["telegram_attempts"])

    logger.info(
        "User %s manually re-queued the Telegram "
        "notification for audit %s",
        request.user.pk,
        audit.pk,
    )
    async_task(
        "api.v1.v1_odk.tasks"
        ".send_telegram_rejection_notification",
        audit.pk,
    )
    return Response(
        {"detail": "Notification re-queued."},
        status=status.HTTP_200_OK,
    )
