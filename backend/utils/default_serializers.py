from rest_framework import serializers


class DefaultResponseSerializer(serializers.Serializer):
    message = serializers.CharField(
        max_length=None,
        min_length=None,
        allow_blank=False,
        trim_whitespace=True,
    )


class DefaultErrorResponseSerializer(serializers.Serializer):
    message = serializers.CharField(
        max_length=None,
        min_length=None,
        required=False,
        trim_whitespace=True,
    )


class CommonOptionSerializer(serializers.Serializer):
    value = serializers.IntegerField()
    label = serializers.CharField()
