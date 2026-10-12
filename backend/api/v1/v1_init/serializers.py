from rest_framework import serializers


class TelegramGroupSerializer(serializers.Serializer):
    chat_id = serializers.CharField(max_length=64)
    # [] means all regions.
    regions = serializers.ListField(
        child=serializers.CharField(), required=False
    )


class TelegramSettingsSerializer(serializers.Serializer):
    """Telegram settings.

    No field declares a default: an omitted key must
    stay omitted so a partial PUT cannot silently
    write "False" over `enabled`, blank out a token,
    or wipe the group list the caller never mentioned.
    """

    enabled = serializers.BooleanField(required=False)
    bot_token = serializers.CharField(
        required=False, allow_blank=True
    )
    groups = TelegramGroupSerializer(
        many=True, required=False
    )

    def validate_groups(self, groups):
        seen = set()
        for group in groups:
            if group["chat_id"] in seen:
                raise serializers.ValidationError(
                    f"Duplicate chat_id: {group['chat_id']}"
                )
            seen.add(group["chat_id"])
        return groups
