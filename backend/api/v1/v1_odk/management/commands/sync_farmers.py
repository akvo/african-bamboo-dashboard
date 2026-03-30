from django.core.management.base import BaseCommand

from api.v1.v1_odk.models import (
    Farmer,
    FormMetadata,
    Plot,
)
from api.v1.v1_odk.utils.farmer_sync import (
    sync_farmers_for_form,
)


class Command(BaseCommand):
    help = (
        "Sync Farmer records from submissions "
        "using FarmerFieldMapping config"
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--form",
            type=str,
            default=None,
            help="asset_uid of a specific form",
        )
        parser.add_argument(
            "--clean",
            action="store_true",
            default=False,
            help=(
                "Delete existing Farmer records "
                "and unlink plots before syncing. "
                "Use with --form to scope cleanup "
                "to a specific form's farmers."
            ),
        )

    def handle(self, *args, **options):
        form_uid = options["form"]
        clean = options["clean"]

        if form_uid:
            try:
                form = FormMetadata.objects.get(
                    asset_uid=form_uid
                )
            except FormMetadata.DoesNotExist:
                self.stderr.write(
                    self.style.ERROR(
                        f"Form {form_uid} not found"
                    )
                )
                return
            forms = [form]
        else:
            forms = FormMetadata.objects.all()

        if clean:
            deleted = self._clean_farmers(forms)
            self.stdout.write(
                self.style.WARNING(
                    f"Cleaned {deleted} farmer(s), "
                    f"unlinked their plots"
                )
            )

        total_created = 0
        total_updated = 0
        total_linked = 0

        for form in forms:
            result = sync_farmers_for_form(form)
            total_created += result["created"]
            total_updated += result["updated"]
            total_linked += result["linked"]
            self.stdout.write(
                f"  {form.asset_uid}: "
                f"created={result['created']} "
                f"updated={result['updated']} "
                f"linked={result['linked']}"
            )

        self.stdout.write(
            self.style.SUCCESS(
                f"Total: created={total_created} "
                f"updated={total_updated} "
                f"linked={total_linked}"
            )
        )

    def _clean_farmers(self, forms):
        """Delete Farmer records linked to the
        given forms' plots and unlink those plots.

        Only deletes farmers that are exclusively
        linked to plots from these forms. Shared
        farmers (linked to plots from other forms)
        are unlinked but not deleted.

        Returns:
            int: number of farmers deleted
        """
        form_ids = [f.pk for f in forms]

        # Find all farmers linked to plots
        # from these forms
        farmer_ids = set(
            Plot.objects.filter(
                form_id__in=form_ids,
                farmer__isnull=False,
            ).values_list(
                "farmer_id", flat=True
            )
        )

        if not farmer_ids:
            return 0

        # Unlink all plots from these forms
        Plot.objects.filter(
            form_id__in=form_ids,
            farmer__isnull=False,
        ).update(farmer=None)

        # Delete farmers that have no remaining
        # plot references (safe for shared farmers)
        orphaned = Farmer.objects.filter(
            pk__in=farmer_ids,
            plots__isnull=True,
        )
        deleted_count = orphaned.count()
        orphaned.delete()

        return deleted_count
