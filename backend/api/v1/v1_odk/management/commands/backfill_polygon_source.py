from django.core.management.base import BaseCommand

from api.v1.v1_odk.models import Plot
from utils.polygon import (
    _extract_first_nonempty,
    _split_csv_fields,
)


class Command(BaseCommand):
    help = (
        "Backfill polygon_source_field for "
        "existing plots by re-extracting from "
        "submission raw_data."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Show what would change "
            "without writing to DB.",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        plots = (
            Plot.objects.filter(
                polygon_source_field__isnull=True,
                submission__isnull=False,
                form__polygon_field__isnull=False,
            )
            .select_related("submission", "form")
        )
        total = plots.count()
        self.stdout.write(
            f"Found {total} plots to backfill."
        )

        updated = []
        skipped = 0
        for plot in plots.iterator():
            raw = plot.submission.raw_data or {}
            fields = _split_csv_fields(
                plot.form.polygon_field
            )
            if not fields:
                skipped += 1
                continue

            _, source_field = (
                _extract_first_nonempty(raw, fields)
            )
            if not source_field:
                skipped += 1
                continue

            plot.polygon_source_field = source_field
            updated.append(plot)

        if dry_run:
            self.stdout.write(
                self.style.WARNING(
                    f"[DRY RUN] Would update "
                    f"{len(updated)} plots, "
                    f"skipped {skipped}."
                )
            )
            for p in updated[:10]:
                self.stdout.write(
                    f"  Plot {p.uuid}: "
                    f"-> {p.polygon_source_field}"
                )
            if len(updated) > 10:
                self.stdout.write(
                    f"  ... and {len(updated) - 10}"
                    f" more"
                )
            return

        if updated:
            Plot.objects.bulk_update(
                updated,
                ["polygon_source_field"],
                batch_size=500,
            )

        self.stdout.write(
            self.style.SUCCESS(
                f"Updated {len(updated)} plots, "
                f"skipped {skipped}."
            )
        )
