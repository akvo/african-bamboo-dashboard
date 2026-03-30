from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        (
            "v1_odk",
            "0012_add_sortable_fields_to_formmetadata",
        ),
    ]

    operations = [
        migrations.AddField(
            model_name="farmerfieldmapping",
            name="uid_start",
            field=models.PositiveIntegerField(
                default=1,
                help_text=(
                    "Minimum starting UID number. "
                    "New farmer UIDs will be "
                    "max(max_existing + 1, "
                    "uid_start). "
                    "Use this to continue numbering "
                    "from a legacy system "
                    "(e.g., 351 to continue after "
                    "AB00350)."
                ),
            ),
        ),
    ]
