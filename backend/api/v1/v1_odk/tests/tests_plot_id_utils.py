from django.test import TestCase

from api.v1.v1_odk.models import (
    FormMetadata,
    MainPlot,
)
from api.v1.v1_odk.utils.plot_id import (
    generate_next_plot_uid,
)


class GenerateNextPlotUidTest(TestCase):
    """Unit tests for generate_next_plot_uid."""

    def setUp(self):
        self.form = FormMetadata.objects.create(
            asset_uid="formUidTest",
            name="UID Test Form",
        )

    def test_first_uid_empty_form(self):
        """First UID for empty form returns
        PLT00001."""
        uid = generate_next_plot_uid(self.form)
        self.assertEqual(uid, "PLT00001")

    def test_respects_plot_uid_start(self):
        """With plot_uid_start=351, first plot is
        PLT00351."""
        self.form.plot_uid_start = 351
        self.form.save()
        uid = generate_next_plot_uid(self.form)
        self.assertEqual(uid, "PLT00351")

    def test_sequential_increment(self):
        """Increments correctly after existing
        plots."""
        MainPlot.objects.create(
            uid="PLT00001", form=self.form,
        )
        uid = generate_next_plot_uid(self.form)
        self.assertEqual(uid, "PLT00002")

    def test_max_wins_over_start(self):
        """If max_existing > start, uses
        max_existing + 1."""
        self.form.plot_uid_start = 5
        self.form.save()
        MainPlot.objects.create(
            uid="PLT00010", form=self.form,
        )
        uid = generate_next_plot_uid(self.form)
        self.assertEqual(uid, "PLT00011")

    def test_start_wins_over_max(self):
        """If start > max_existing + 1, uses
        start."""
        self.form.plot_uid_start = 100
        self.form.save()
        MainPlot.objects.create(
            uid="PLT00005", form=self.form,
        )
        uid = generate_next_plot_uid(self.form)
        self.assertEqual(uid, "PLT00100")

    def test_scoped_per_form(self):
        """UIDs are scoped per form — other form's
        plots don't affect numbering."""
        other_form = FormMetadata.objects.create(
            asset_uid="formOther",
            name="Other Form",
        )
        MainPlot.objects.create(
            uid="PLT00050", form=other_form,
        )
        uid = generate_next_plot_uid(self.form)
        self.assertEqual(uid, "PLT00001")
