import logging

from django.core.management.base import (
    BaseCommand,
)

from api.v1.v1_odk.constants import (
    ApprovalStatusTypes,
)
from api.v1.v1_odk.models import (
    FormMetadata,
    MainPlotSubmission,
    Submission,
)
from api.v1.v1_odk.utils.plot_id import (
    create_main_plot_for_submission,
)

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = (
        "Backfill Plot IDs (MainPlot) for "
        "approved submissions that were approved "
        "before the Plot ID feature was deployed."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help=(
                "Show what would be created "
                "without saving."
            ),
        )
        parser.add_argument(
            "--form-id",
            type=str,
            default=None,
            help=(
                "Only backfill for a specific "
                "form (asset_uid)."
            ),
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        form_id = options["form_id"]

        qs = Submission.objects.filter(
            approval_status=(
                ApprovalStatusTypes.APPROVED
            ),
        ).exclude(
            pk__in=MainPlotSubmission.objects.values_list(
                "submission_id", flat=True
            ),
        ).select_related("form", "plot").order_by(
            "submission_time",
        )

        if form_id:
            try:
                form = FormMetadata.objects.get(
                    asset_uid=form_id,
                )
                qs = qs.filter(form=form)
            except FormMetadata.DoesNotExist:
                self.stderr.write(
                    f"Form {form_id} not found."
                )
                return

        total = qs.count()
        self.stdout.write(
            f"Found {total} approved submissions "
            f"without Plot IDs."
        )

        if total == 0:
            self.stdout.write("Nothing to do.")
            return

        if dry_run:
            self.stdout.write(
                "[DRY RUN] Would create "
                f"{total} Plot IDs."
            )
            for sub in qs[:10]:
                self.stdout.write(
                    f"  - {sub.uuid} "
                    f"(form={sub.form.asset_uid})"
                )
            if total > 10:
                self.stdout.write(
                    f"  ... and {total - 10} more"
                )
            return

        created = 0
        skipped = 0
        for sub in qs.iterator():
            main_plot = (
                create_main_plot_for_submission(sub)
            )
            if main_plot:
                created += 1
                logger.info(
                    "Created %s for submission %s",
                    main_plot.uid,
                    sub.uuid,
                )
            else:
                skipped += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"Done. Created {created} Plot IDs, "
                f"skipped {skipped}."
            )
        )
