from django.core.management.base import (
    BaseCommand,
)

from api.v1.v1_odk.models import Plot
from api.v1.v1_odk.utils.flagged_reason_converter import (
    convert_flagged_reason,
)


class Command(BaseCommand):
    help = (
        "Convert legacy string flagged_reason "
        "values to JSON format."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Preview without saving.",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        converted = 0
        skipped = 0
        already_json = 0

        plots = Plot.objects.exclude(
            flagged_reason__isnull=True
        )

        for plot in plots.iterator():
            reason = plot.flagged_reason
            if isinstance(reason, list):
                already_json += 1
                continue

            result = convert_flagged_reason(reason)
            if result is None:
                skipped += 1
                continue

            if dry_run:
                self.stdout.write(
                    f"  Plot {plot.uuid}: "
                    f"{reason!r} → {result}"
                )
            else:
                plot.flagged_reason = result
                plot.save(
                    update_fields=["flagged_reason"]
                )
            converted += 1

        prefix = "[DRY RUN] " if dry_run else ""
        self.stdout.write(
            self.style.SUCCESS(
                f"{prefix}"
                f"Converted: {converted}, "
                f"Skipped: {skipped}, "
                f"Already JSON: {already_json}"
            )
        )
