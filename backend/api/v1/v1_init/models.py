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


class TelegramGroup(models.Model):
    """A Telegram chat that receives rejection alerts
    for the regions it is scoped to."""

    # Unique so two rows can never target one chat.
    chat_id = models.CharField(max_length=64, unique=True)
    # Cached Telegram title, display only. Refreshed on
    # Re-sync so the table renders while Telegram is
    # unreachable.
    title = models.CharField(max_length=255, blank=True)
    # Exact Plot.region values. [] means all regions.
    regions = models.JSONField(default=list, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.title or self.chat_id
