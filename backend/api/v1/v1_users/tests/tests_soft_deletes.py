from django.test import TestCase

from api.v1.v1_users.models import SystemUser


def _create_user(email, name="test"):
    return SystemUser.objects._create_user(
        email=email,
        password="Test1234",
        name=name,
    )


class SoftDeletesQuerySetTest(TestCase):
    """QuerySet-level bulk operations."""

    def setUp(self):
        self.u1 = _create_user("a@test.org", "a")
        self.u2 = _create_user("b@test.org", "b")

    def test_only_deleted(self):
        self.u1.soft_delete()
        qs = (
            SystemUser.objects_with_deleted.all()
            .only_deleted()
        )
        self.assertEqual(qs.count(), 1)
        self.assertEqual(qs.first().pk, self.u1.pk)

    def test_bulk_soft_delete(self):
        SystemUser.objects.all().soft_delete()
        self.assertEqual(
            SystemUser.objects.count(), 0
        )
        self.assertEqual(
            SystemUser.objects_with_deleted.count(),
            2,
        )

    def test_bulk_hard_delete(self):
        SystemUser.objects.all().hard_delete()
        self.assertEqual(
            SystemUser.objects_with_deleted.count(),
            0,
        )

    def test_bulk_restore(self):
        SystemUser.objects.all().soft_delete()
        self.assertEqual(
            SystemUser.objects.count(), 0
        )
        SystemUser.objects_deleted.all().restore()
        self.assertEqual(
            SystemUser.objects.count(), 2
        )


class SoftDeletesManagerTest(TestCase):
    """Manager-level operations."""

    def setUp(self):
        self.u1 = _create_user("a@test.org", "a")
        self.u2 = _create_user("b@test.org", "b")

    def test_objects_excludes_deleted(self):
        self.u1.soft_delete()
        self.assertEqual(
            SystemUser.objects.count(), 1
        )

    def test_objects_deleted_only(self):
        self.u1.soft_delete()
        self.assertEqual(
            SystemUser.objects_deleted.count(), 1
        )
        self.assertEqual(
            SystemUser.objects_deleted.first().pk,
            self.u1.pk,
        )

    def test_objects_with_deleted_includes_all(self):
        self.u1.soft_delete()
        self.assertEqual(
            SystemUser.objects_with_deleted.count(),
            2,
        )

    def test_manager_soft_delete(self):
        SystemUser.objects.soft_delete()
        self.assertEqual(
            SystemUser.objects.count(), 0
        )
        self.assertEqual(
            SystemUser.objects_deleted.count(), 2
        )

    def test_manager_hard_delete(self):
        SystemUser.objects.hard_delete()
        self.assertEqual(
            SystemUser.objects_with_deleted.count(),
            0,
        )

    def test_manager_restore(self):
        SystemUser.objects.soft_delete()
        SystemUser.objects_deleted.restore()
        self.assertEqual(
            SystemUser.objects.count(), 2
        )


class SoftDeletesInstanceTest(TestCase):
    """Instance-level methods."""

    def setUp(self):
        self.user = _create_user("a@test.org")

    def test_soft_delete(self):
        self.user.soft_delete()
        self.assertIsNotNone(self.user.deleted_at)
        self.assertEqual(
            SystemUser.objects.count(), 0
        )

    def test_hard_delete(self):
        pk = self.user.pk
        self.user.hard_delete()
        exists = SystemUser.objects_with_deleted.filter(
            pk=pk
        ).exists()
        self.assertFalse(exists)

    def test_restore(self):
        self.user.soft_delete()
        self.user.restore()
        self.assertIsNone(self.user.deleted_at)
        self.assertEqual(
            SystemUser.objects.count(), 1
        )
