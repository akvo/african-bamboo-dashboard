from unittest.mock import patch

from django.test import TestCase
from django.test.utils import override_settings

from api.v1.v1_odk.models import FormMetadata, FormOption, FormQuestion
from api.v1.v1_odk.tests.mixins import OdkTestHelperMixin


def make_asset_content(survey=None, choices=None):
    return {
        "survey": survey or [],
        "choices": choices or [],
    }


SAMPLE_SURVEY = [
    {
        "name": "start",
        "type": "start",
        "$xpath": "start",
    },
    {
        "name": "region",
        "type": "select_one",
        "select_from_list_name": "regions",
        "label": ["Region"],
        "$xpath": "region",
    },
    {
        "name": "woreda",
        "type": "select_one",
        "select_from_list_name": "woredas",
        "label": ["Woreda"],
        "$xpath": "woreda",
    },
    {
        "name": "crops",
        "type": "select_multiple",
        "select_from_list_name": "crop_list",
        "label": ["Crops grown"],
        "$xpath": "crops",
    },
    {
        "name": "full_name",
        "type": "text",
        "label": ["Full name"],
        "$xpath": "consent/full_name",
    },
]

SAMPLE_CHOICES = [
    {
        "list_name": "regions",
        "name": "ET04",
        "label": ["Oromia"],
    },
    {
        "list_name": "regions",
        "name": "ET07",
        "label": ["SNNPR"],
    },
    {
        "list_name": "woredas",
        "name": "W01",
        "label": ["Jimma"],
    },
    {
        "list_name": "crop_list",
        "name": "bamboo",
        "label": ["Bamboo"],
    },
    {
        "list_name": "crop_list",
        "name": "coffee",
        "label": ["Coffee"],
    },
]


@override_settings(USE_TZ=False, TEST_ENV=True)
class SyncQuestionsTest(TestCase, OdkTestHelperMixin):
    def setUp(self):
        self.user = self.create_kobo_user()
        self.auth = self.get_auth_header()
        self.form = FormMetadata.objects.create(
            asset_uid="formQ",
            name="Question Form",
        )

    @patch("api.v1.v1_odk.views.KoboClient")
    def test_sync_populates_questions(self, mock_client_cls):
        mock = mock_client_cls.return_value
        mock.get_asset_detail.return_value = make_asset_content(
            SAMPLE_SURVEY, SAMPLE_CHOICES
        )
        mock.fetch_all_submissions.return_value = []
        resp = self.client.post(
            "/api/v1/odk/forms/formQ/sync/",
            content_type="application/json",
            **self.auth,
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        # start is skipped, 4 questions created
        self.assertEqual(data["questions_synced"], 4)
        self.assertEqual(
            FormQuestion.objects.filter(form=self.form).count(),
            4,
        )

    @patch("api.v1.v1_odk.views.KoboClient")
    def test_sync_populates_options(self, mock_client_cls):
        mock = mock_client_cls.return_value
        mock.get_asset_detail.return_value = make_asset_content(
            SAMPLE_SURVEY, SAMPLE_CHOICES
        )
        mock.fetch_all_submissions.return_value = []
        self.client.post(
            "/api/v1/odk/forms/formQ/sync/",
            content_type="application/json",
            **self.auth,
        )
        region_q = FormQuestion.objects.get(form=self.form, name="region")
        self.assertEqual(region_q.options.count(), 2)
        opt_names = set(region_q.options.values_list("name", flat=True))
        self.assertEqual(opt_names, {"ET04", "ET07"})
        # Check label
        et04 = region_q.options.get(name="ET04")
        self.assertEqual(et04.label, "Oromia")

    @patch("api.v1.v1_odk.views.KoboClient")
    def test_resync_replaces_questions(self, mock_client_cls):
        mock = mock_client_cls.return_value
        mock.get_asset_detail.return_value = make_asset_content(
            SAMPLE_SURVEY, SAMPLE_CHOICES
        )
        mock.fetch_all_submissions.return_value = []
        # First sync
        self.client.post(
            "/api/v1/odk/forms/formQ/sync/",
            content_type="application/json",
            **self.auth,
        )
        first_ids = set(
            FormQuestion.objects.filter(form=self.form).values_list(
                "id", flat=True
            )
        )

        # Second sync with different survey
        mock.get_asset_detail.return_value = make_asset_content(
            [
                {
                    "name": "age",
                    "type": "integer",
                    "label": ["Age"],
                    "$xpath": "age",
                },
            ],
            [],
        )
        self.client.post(
            "/api/v1/odk/forms/formQ/sync/",
            content_type="application/json",
            **self.auth,
        )
        second_ids = set(
            FormQuestion.objects.filter(form=self.form).values_list(
                "id", flat=True
            )
        )
        self.assertEqual(
            FormQuestion.objects.filter(form=self.form).count(),
            1,
        )
        # IDs should be different
        self.assertTrue(first_ids.isdisjoint(second_ids))
        # Old options gone
        self.assertEqual(
            FormOption.objects.filter(question__form=self.form).count(),
            0,
        )

    @patch("api.v1.v1_odk.views.KoboClient")
    def test_select_multiple_stored(self, mock_client_cls):
        mock = mock_client_cls.return_value
        mock.get_asset_detail.return_value = make_asset_content(
            SAMPLE_SURVEY, SAMPLE_CHOICES
        )
        mock.fetch_all_submissions.return_value = []
        self.client.post(
            "/api/v1/odk/forms/formQ/sync/",
            content_type="application/json",
            **self.auth,
        )
        crops_q = FormQuestion.objects.get(form=self.form, name="crops")
        self.assertEqual(crops_q.type, "select_multiple")
        self.assertEqual(crops_q.options.count(), 2)

    @patch("api.v1.v1_odk.views.KoboClient")
    def test_sync_continues_on_asset_detail_failure(self, mock_client_cls):
        mock = mock_client_cls.return_value
        mock.get_asset_detail.side_effect = Exception("API error")
        mock.fetch_all_submissions.return_value = [
            {
                "_uuid": "uuid-q1",
                "_id": 1,
                "_submission_time": ("2024-01-15T10:30:00+00:00"),
                "_submitted_by": "user1",
                "meta/instanceName": "inst1",
                "_geolocation": [9.0, 38.7],
                "_tags": [],
            },
        ]
        resp = self.client.post(
            "/api/v1/odk/forms/formQ/sync/",
            content_type="application/json",
            **self.auth,
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["questions_synced"], 0)
        self.assertEqual(data["synced"], 1)

    @patch("api.v1.v1_odk.views.KoboClient")
    def test_xpath_used_as_question_name(self, mock_client_cls):
        mock = mock_client_cls.return_value
        mock.get_asset_detail.return_value = make_asset_content(
            SAMPLE_SURVEY, SAMPLE_CHOICES
        )
        mock.fetch_all_submissions.return_value = []
        self.client.post(
            "/api/v1/odk/forms/formQ/sync/",
            content_type="application/json",
            **self.auth,
        )
        # full_name has $xpath = "consent/full_name"
        self.assertTrue(
            FormQuestion.objects.filter(
                form=self.form,
                name="consent/full_name",
            ).exists()
        )

    @patch("api.v1.v1_odk.views.KoboClient")
    def test_fallback_type_parsing(self, mock_client_cls):
        """Test combined 'select_one list_name'
        format."""
        mock = mock_client_cls.return_value
        mock.get_asset_detail.return_value = make_asset_content(
            [
                {
                    "name": "status",
                    "type": "select_one statuses",
                    "label": ["Status"],
                    "$xpath": "status",
                },
            ],
            [
                {
                    "list_name": "statuses",
                    "name": "active",
                    "label": ["Active"],
                },
                {
                    "list_name": "statuses",
                    "name": "inactive",
                    "label": ["Inactive"],
                },
            ],
        )
        mock.fetch_all_submissions.return_value = []
        self.client.post(
            "/api/v1/odk/forms/formQ/sync/",
            content_type="application/json",
            **self.auth,
        )
        q = FormQuestion.objects.get(form=self.form, name="status")
        self.assertEqual(q.type, "select_one")
        self.assertEqual(q.options.count(), 2)
