from uuid import uuid4

from django.contrib.auth.base_user import BaseUserManager

from utils.soft_deletes_model import SoftDeletesManager


class UserManager(BaseUserManager, SoftDeletesManager):
    use_in_migrations = True

    def _create_user(self, email, password, **extra_fields):
        """
        Creates and saves a User with the given email and password.
        """
        if not email:
            raise ValueError("The given email must be set")
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.email_verification_code = uuid4()
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password, **extra_fields):
        extra_fields.setdefault("is_superuser", True)
        return self._create_user(email, password, **extra_fields)
