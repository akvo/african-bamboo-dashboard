from django.db import migrations, models


FORWARD_SQL = """
ALTER TABLE plots
ALTER COLUMN flagged_reason
TYPE jsonb
USING CASE
    WHEN flagged_reason IS NULL THEN NULL
    ELSE jsonb_build_array(
        jsonb_build_object(
            'type',
            CASE
                WHEN flagged_reason
                    LIKE '%%overlaps with%%'
                    THEN 'OVERLAP'
                WHEN flagged_reason
                    ILIKE '%%too few vertices%%'
                    THEN 'GEOMETRY_TOO_FEW_VERTICES'
                WHEN flagged_reason
                    ILIKE '%%intersect%%'
                    THEN 'GEOMETRY_SELF_INTERSECT'
                WHEN flagged_reason
                    ILIKE '%%too small%%'
                    THEN 'GEOMETRY_AREA_TOO_SMALL'
                WHEN flagged_reason
                    LIKE '%%No polygon data%%'
                    THEN 'GEOMETRY_NO_DATA'
                WHEN flagged_reason
                    LIKE '%%Failed to parse%%'
                    THEN 'GEOMETRY_PARSE_FAIL'
                ELSE 'GEOMETRY_PARSE_FAIL'
            END,
            'severity', 'error',
            'note', flagged_reason
        )
    )
END;
"""

REVERSE_SQL = """
ALTER TABLE plots
ALTER COLUMN flagged_reason
TYPE varchar(500)
USING CASE
    WHEN flagged_reason IS NULL THEN NULL
    WHEN jsonb_typeof(flagged_reason) = 'array'
        AND jsonb_array_length(flagged_reason) > 0
        THEN (
            flagged_reason->0->>'note'
        )::varchar(500)
    ELSE NULL
END;
"""


class Migration(migrations.Migration):

    dependencies = [
        (
            "v1_odk",
            "0009_submission_unique_form_kobo_id",
        ),
    ]

    operations = [
        migrations.RunSQL(
            sql=FORWARD_SQL,
            reverse_sql=REVERSE_SQL,
            state_operations=[
                migrations.AlterField(
                    model_name="plot",
                    name="flagged_reason",
                    field=models.JSONField(
                        blank=True,
                        default=None,
                        help_text=(
                            "List of flags: "
                            "[{type, severity, note}]"
                        ),
                        null=True,
                    ),
                ),
            ],
        ),
    ]
