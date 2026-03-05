from rest_framework import serializers


class TelegramSettingsSerializer(serializers.Serializer):
    enabled = serializers.BooleanField(default=False)
    bot_token = serializers.CharField(
        required=False, allow_blank=True, default=""
    )
    supervisor_group_id = serializers.CharField(
        required=False, allow_blank=True, default=""
    )
    enumerator_group_id = serializers.CharField(
        required=False, allow_blank=True, default=""
    )
