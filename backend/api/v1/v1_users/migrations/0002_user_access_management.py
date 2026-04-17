from django.db import migrations, models
from django.db.models import Q


def backfill_existing_users_to_active(apps, schema_editor):
    # UserStatus.ACTIVE = 1. Literal used here so that future
    # renames of the constant cannot break this migration.
    SystemUser = apps.get_model("v1_users", "SystemUser")
    SystemUser.objects.update(status=1, is_active=True)


def revert_backfill(apps, schema_editor):
    # Data migration is intentionally not safely reversible.
    # The schema reverse drops the status column anyway.
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("v1_users", "0001_initial"),
    ]

    operations = [
        migrations.AlterUniqueTogether(
            name="systemuser",
            unique_together=set(),
        ),
        migrations.AlterField(
            model_name="systemuser",
            name="kobo_username",
            field=models.CharField(
                blank=True,
                help_text="KoboToolbox username",
                max_length=255,
                null=True,
            ),
        ),
        migrations.AddField(
            model_name="systemuser",
            name="is_active",
            field=models.BooleanField(default=True),
        ),
        migrations.AddField(
            model_name="systemuser",
            name="status",
            field=models.IntegerField(
                choices=[
                    (0, "pending"),
                    (1, "active"),
                    (2, "suspended"),
                ],
                default=0,
            ),
        ),
        migrations.AddField(
            model_name="systemuser",
            name="status_changed_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="systemuser",
            name="status_changed_by",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=models.deletion.SET_NULL,
                related_name="+",
                to="v1_users.systemuser",
            ),
        ),
        migrations.AddField(
            model_name="systemuser",
            name="invited_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddConstraint(
            model_name="systemuser",
            constraint=models.UniqueConstraint(
                condition=Q(kobo_username__isnull=False),
                fields=("kobo_username", "kobo_url"),
                name="unique_kobo_identity_when_set",
            ),
        ),
        migrations.RunPython(
            backfill_existing_users_to_active,
            revert_backfill,
        ),
    ]
