from django.test import TestCase

from api.v1.v1_users.models import SystemUser, UserStatus


class UserModelTestCase(TestCase):
    def setUp(self):
        self.user = SystemUser.objects._create_user(
            email="test@test.org",
            password="Test1234",
            name="test",
            status=UserStatus.ACTIVE,
        )

    def test_get_sign_pk(self):
        self.assertTrue(self.user.get_sign_pk)

    def test_soft_delete_user(self):
        self.user.soft_delete()
        self.assertIsNotNone(self.user.id)
        self.assertTrue(self.user.deleted_at)

    def test_restore_deleted_user(self):
        self.user.restore()
        self.assertIsNone(self.user.deleted_at)

    def test_hard_delete_user(self):
        self.user.delete(hard=True)
        total_users = SystemUser.objects.count()
        self.assertEqual(total_users, 0)

    def test_create_user_without_email(self):
        with self.assertRaises(ValueError) as context:
            SystemUser.objects._create_user(
                email=None,
                password="test1234",
                name="test",
            )
        self.assertEqual(
            str(context.exception), "The given email must be set"
        )

    def test_successfully_created_superuser(self):
        admin = SystemUser.objects.create_superuser(
            email="admin@mail.com", password="admin", name="admin"
        )
        self.assertIsNotNone(admin.id)
        total_admin = SystemUser.objects.filter(
            is_superuser=True
        ).count()
        self.assertEqual(total_admin, 1)

    def test_new_user_defaults_to_pending(self):
        """A user created without an explicit status must land
        in PENDING — this is the gate for fresh sign-ups."""
        user = SystemUser.objects._create_user(
            email="fresh@test.org",
            password="Test1234",
            name="fresh",
        )
        self.assertEqual(user.status, UserStatus.PENDING)

    def test_user_status_fieldstr_labels(self):
        """fieldStr maps integer values to lowercase string
        labels — this shape is what the 403 login response
        serializes."""
        self.assertEqual(
            UserStatus.fieldStr[UserStatus.PENDING], "pending"
        )
        self.assertEqual(
            UserStatus.fieldStr[UserStatus.ACTIVE], "active"
        )
        self.assertEqual(
            UserStatus.fieldStr[UserStatus.SUSPENDED], "suspended"
        )
