from django.db import models


class SystemSetting(models.Model):
    group = models.CharField(max_length=100)
    key = models.CharField(max_length=100)
    value = models.TextField(default="")
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("group", "key")

    def __str__(self):
        return f"{self.group}.{self.key}"
