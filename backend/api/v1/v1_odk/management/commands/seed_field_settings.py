from django.core.management.base import BaseCommand

from api.v1.v1_odk.models import FieldSettings
from api.v1.v1_odk.constants import DEFAULT_FIELDS


class Command(BaseCommand):
    help = "Seed default FieldSettings entries"

    def handle(self, *args, **options):
        created_count = 0
        for name in DEFAULT_FIELDS:
            _, created = (
                FieldSettings.objects.get_or_create(
                    name=name
                )
            )
            if created:
                created_count += 1
        self.stdout.write(
            self.style.SUCCESS(
                f"Seeded {created_count} new "
                f"FieldSettings "
                f"({len(DEFAULT_FIELDS)} total)"
            )
        )
