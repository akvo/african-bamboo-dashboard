from django.core.management.base import BaseCommand

from api.v1.v1_odk.models import FormMetadata
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

    def handle(self, *args, **options):
        form_uid = options["form"]

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
