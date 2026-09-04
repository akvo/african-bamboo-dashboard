from rest_framework import serializers


class TelegramSettingsSerializer(serializers.Serializer):
    """Telegram settings.

    No field declares a default: an omitted key must
    stay omitted so a partial PUT cannot silently
    write "False" over `enabled` or blank out a
    token the caller never mentioned.
    """

    enabled = serializers.BooleanField(required=False)
    bot_token = serializers.CharField(
        required=False, allow_blank=True
    )
    supervisor_group_id = serializers.CharField(
        required=False, allow_blank=True
    )
    enumerator_group_id = serializers.CharField(
        required=False, allow_blank=True
    )
