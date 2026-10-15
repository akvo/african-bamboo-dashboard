from django.db import models


class A2FSnapshot(models.Model):
    """The latest access to finance workbook, one sheet per field.

    Always replaced whole by ``import_a2f``; there is never more
    than one row and no history.
    """

    data_as_of = models.DateField()
    parameters = models.JSONField()
    cooperatives = models.JSONField()
    members = models.JSONField()
    loans = models.JSONField()
    parcels = models.JSONField()
    imported_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "a2f_snapshot"
