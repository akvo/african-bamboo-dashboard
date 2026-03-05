from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="SystemSetting",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "group",
                    models.CharField(max_length=100),
                ),
                (
                    "key",
                    models.CharField(max_length=100),
                ),
                (
                    "value",
                    models.TextField(default=""),
                ),
                (
                    "updated_at",
                    models.DateTimeField(
                        auto_now=True
                    ),
                ),
            ],
            options={
                "unique_together": {
                    ("group", "key")
                },
            },
        ),
    ]
