import logging

from django.core.management.base import (
    BaseCommand,
)

from api.v1.v1_odk.constants import (
    ApprovalStatusTypes,
)
from api.v1.v1_odk.models import Submission

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = (
        "Backfill approval_status from "
        "raw_data._validation_status for "
        "submissions synced before the "
        "ReverseKoboStatusMap was added."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Show what would be updated "
            "without saving.",
        )
        parser.add_argument(
            "--instance-name",
            type=str,
            default=None,
            help="Process a single submission "
            "by instance name.",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        instance_name = options["instance_name"]

        qs = Submission.objects.exclude(
            raw_data__isnull=True,
        )
        if instance_name:
            qs = qs.filter(
                instance_name=instance_name,
            )

        checked = 0
        updated = 0
        skipped = 0

        reverse_map = (
            ApprovalStatusTypes.ReverseKoboStatusMap
        )

        for sub in qs.iterator():
            checked += 1
            raw = sub.raw_data or {}
            validation = raw.get(
                "_validation_status", {}
            )
            if not isinstance(validation, dict):
                skipped += 1
                continue

            uid = validation.get("uid")
            if not uid:
                skipped += 1
                continue

            if uid not in reverse_map:
                skipped += 1
                logger.warning(
                    "Unknown validation uid "
                    "'%s' for submission %s",
                    uid,
                    sub.instance_name or sub.uuid,
                )
                continue

            expected = reverse_map[uid]
            if sub.approval_status == expected:
                skipped += 1
                continue

            if dry_run:
                self.stdout.write(
                    f"  Would update "
                    f"{sub.instance_name or sub.uuid}"
                    f": {sub.approval_status}"
                    f" -> {expected}"
                )
            else:
                sub.approval_status = expected
                sub.save(
                    update_fields=[
                        "approval_status"
                    ]
                )

            updated += 1

        if dry_run:
            self.stdout.write(
                self.style.WARNING(
                    f"[DRY RUN] Checked "
                    f"{checked}, would update "
                    f"{updated}, skipped "
                    f"{skipped}."
                )
            )
        else:
            self.stdout.write(
                self.style.SUCCESS(
                    f"Checked {checked}, "
                    f"updated {updated}, "
                    f"skipped {skipped}."
                )
            )
