from rest_framework import serializers

from api.v1.v1_users.models import SystemUser
from utils.custom_serializer_fields import (CustomCharField, CustomEmailField,
                                            CustomUrlField)


class LoginSerializer(serializers.Serializer):
    kobo_url = CustomUrlField()
    kobo_username = CustomCharField()
    kobo_password = CustomCharField()


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = SystemUser
        fields = [
            "id",
            "name",
            "email",
            "kobo_url",
            "kobo_username",
        ]


class LoginResponseSerializer(serializers.Serializer):
    user = UserSerializer()
    token = serializers.CharField()
    expiration_time = serializers.DateTimeField()


class ResendVerificationEmailSerializer(serializers.Serializer):
    email = CustomEmailField()

    def validate_email(self, value):
        current_user = self.context.get("user")
        if current_user.email != value:
            raise serializers.ValidationError("Email address not found.")
        return value


class UpdateUserSerializer(serializers.ModelSerializer):
    name = CustomCharField(
        required=False,
        allow_null=True,
    )
    email = CustomEmailField(
        required=False,
        allow_null=True,
    )

    class Meta:
        model = SystemUser
        fields = [
            "name",
            "email",
        ]

    def update(self, instance, validated_data):
        instance = super().update(instance, validated_data)
        return instance
