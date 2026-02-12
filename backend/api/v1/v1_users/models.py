from django.contrib.auth.base_user import AbstractBaseUser
from django.contrib.auth.models import PermissionsMixin
from django.core import signing
from django.db import models

from utils.custom_manager import UserManager
from utils.soft_deletes_model import SoftDeletes


class SystemUser(AbstractBaseUser, PermissionsMixin, SoftDeletes):
    email = models.EmailField(unique=True)
    name = models.CharField(max_length=100)

    kobo_url = models.URLField(
        max_length=500,
        null=True,
        blank=True,
        help_text="KoboToolbox server URL",
    )
    kobo_username = models.CharField(
        max_length=255,
        null=True,
        blank=True,
        help_text="KoboToolbox username",
    )
    kobo_password = models.TextField(
        null=True,
        blank=True,
        help_text="Encrypted KoboToolbox password",
    )

    objects = UserManager()

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["name"]

    def delete(
        self,
        using=None,
        keep_parents=False,
        hard: bool = False,
    ):
        return super().delete(
            using=using,
            keep_parents=keep_parents,
            hard=hard,
        )

    def get_sign_pk(self):
        return signing.dumps(self.pk)

    @property
    def is_staff(self):
        return self.is_superuser

    class Meta:
        db_table = "system_user"
        unique_together = [("kobo_username", "kobo_url")]
