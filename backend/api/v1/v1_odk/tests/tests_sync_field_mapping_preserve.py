from django.test import TestCase

from api.v1.v1_odk.funcs import (
    sync_form_questions,
)
from api.v1.v1_odk.models import (
    FieldMapping,
    FieldSettings,
    FormMetadata,
    FormOption,
    FormQuestion,
)


def _make_content(survey, choices=None):
    """Build a KoboToolbox asset content dict."""
    return {
        "survey": survey,
        "choices": choices or [],
    }


def _text_field(name, label=None):
    return {
        "type": "text",
        "name": name,
        "$xpath": name,
        "label": [label or name],
    }


def _select_field(name, list_name, label=None):
    return {
        "type": "select_one",
        "name": name,
        "$xpath": name,
        "label": [label or name],
        "select_from_list_name": list_name,
    }


class SyncPreservesFieldMappingsTest(TestCase):
    """sync_form_questions must preserve
    FieldMapping records across question
    rebuilds."""

    def setUp(self):
        self.form = FormMetadata.objects.create(
            asset_uid="syncPreserve",
            name="Sync Preserve Form",
        )
        # Seed field settings
        self.fs_farmer = (
            FieldSettings.objects.create(
                name="farmer"
            )
        )
        self.fs_region = (
            FieldSettings.objects.create(
                name="region"
            )
        )
        self.fs_phone = (
            FieldSettings.objects.create(
                name="phone_number"
            )
        )

    def _initial_sync(self):
        """Run first sync and create mappings."""
        content = _make_content(
            survey=[
                _text_field(
                    "farmer_name", "Farmer"
                ),
                _text_field(
                    "region_name", "Region"
                ),
                _text_field("phone", "Phone"),
            ]
        )
        sync_form_questions(self.form, content)

        q_farmer = FormQuestion.objects.get(
            form=self.form, name="farmer_name"
        )
        q_region = FormQuestion.objects.get(
            form=self.form, name="region_name"
        )
        FieldMapping.objects.create(
            field=self.fs_farmer,
            form=self.form,
            form_question=q_farmer,
        )
        FieldMapping.objects.create(
            field=self.fs_region,
            form=self.form,
            form_question=q_region,
        )
        return q_farmer, q_region

    def test_mappings_preserved_after_sync(self):
        """Mappings survive when questions are
        rebuilt with the same names."""
        self._initial_sync()
        self.assertEqual(
            FieldMapping.objects.filter(
                form=self.form
            ).count(),
            2,
        )

        # Second sync with same questions
        content = _make_content(
            survey=[
                _text_field(
                    "farmer_name", "Farmer"
                ),
                _text_field(
                    "region_name", "Region"
                ),
                _text_field("phone", "Phone"),
            ]
        )
        sync_form_questions(self.form, content)

        mappings = FieldMapping.objects.filter(
            form=self.form
        )
        self.assertEqual(mappings.count(), 2)

        names = set(
            mappings.values_list(
                "field__name", flat=True
            )
        )
        self.assertEqual(
            names, {"farmer", "region"}
        )

        # Verify they point to the new question PKs
        for m in mappings:
            self.assertEqual(
                m.form_question.form_id,
                self.form.pk,
            )

    def test_mappings_point_to_new_question_pks(
        self,
    ):
        """After sync, mappings reference newly
        created FormQuestion PKs, not stale ones."""
        old_farmer, _ = self._initial_sync()
        old_pk = old_farmer.pk

        content = _make_content(
            survey=[
                _text_field(
                    "farmer_name", "Farmer v2"
                ),
                _text_field(
                    "region_name", "Region"
                ),
                _text_field("phone", "Phone"),
            ]
        )
        sync_form_questions(self.form, content)

        mapping = FieldMapping.objects.get(
            field=self.fs_farmer, form=self.form
        )
        # Must be a different PK (new question)
        self.assertNotEqual(
            mapping.form_question.pk, old_pk
        )
        self.assertEqual(
            mapping.form_question.name,
            "farmer_name",
        )
        # Label updated to new version
        self.assertEqual(
            mapping.form_question.label,
            "Farmer v2",
        )

    def test_mapping_dropped_when_question_removed(
        self,
    ):
        """If a mapped question is removed from
        the form, that mapping is silently dropped."""
        self._initial_sync()

        # Re-sync without farmer_name question
        content = _make_content(
            survey=[
                _text_field(
                    "region_name", "Region"
                ),
                _text_field("phone", "Phone"),
            ]
        )
        sync_form_questions(self.form, content)

        mappings = FieldMapping.objects.filter(
            form=self.form
        )
        self.assertEqual(mappings.count(), 1)
        self.assertEqual(
            mappings.first().field.name, "region"
        )

    def test_mapping_dropped_when_question_renamed(
        self,
    ):
        """If a mapped question is renamed, the old
        mapping is dropped (name no longer matches)."""
        self._initial_sync()

        # Re-sync with farmer_name renamed
        content = _make_content(
            survey=[
                _text_field(
                    "farmer_full_name",
                    "Farmer Full Name",
                ),
                _text_field(
                    "region_name", "Region"
                ),
                _text_field("phone", "Phone"),
            ]
        )
        sync_form_questions(self.form, content)

        farmer_mapping = (
            FieldMapping.objects.filter(
                field=self.fs_farmer,
                form=self.form,
            )
        )
        self.assertFalse(farmer_mapping.exists())

        # region mapping still intact
        region_mapping = (
            FieldMapping.objects.filter(
                field=self.fs_region,
                form=self.form,
            )
        )
        self.assertTrue(region_mapping.exists())

    def test_no_mappings_to_preserve(self):
        """Sync works normally when no field
        mappings exist."""
        content = _make_content(
            survey=[
                _text_field(
                    "farmer_name", "Farmer"
                ),
            ]
        )
        sync_form_questions(self.form, content)

        self.assertEqual(
            FormQuestion.objects.filter(
                form=self.form
            ).count(),
            1,
        )
        self.assertEqual(
            FieldMapping.objects.filter(
                form=self.form
            ).count(),
            0,
        )

    def test_options_recreated_with_questions(self):
        """FormOption records are rebuilt correctly
        alongside question rebuild."""
        content = _make_content(
            survey=[
                _select_field(
                    "status",
                    "status_list",
                    "Status",
                ),
            ],
            choices=[
                {
                    "list_name": "status_list",
                    "name": "active",
                    "label": ["Active"],
                },
                {
                    "list_name": "status_list",
                    "name": "inactive",
                    "label": ["Inactive"],
                },
            ],
        )
        sync_form_questions(self.form, content)
        self.assertEqual(
            FormOption.objects.filter(
                question__form=self.form
            ).count(),
            2,
        )

        # Map to the select question
        q = FormQuestion.objects.get(
            form=self.form, name="status"
        )
        FieldMapping.objects.create(
            field=self.fs_farmer,
            form=self.form,
            form_question=q,
        )

        # Re-sync with updated options
        content["choices"].append(
            {
                "list_name": "status_list",
                "name": "pending",
                "label": ["Pending"],
            }
        )
        sync_form_questions(self.form, content)

        # Options updated
        self.assertEqual(
            FormOption.objects.filter(
                question__form=self.form
            ).count(),
            3,
        )
        # Mapping preserved
        self.assertTrue(
            FieldMapping.objects.filter(
                field=self.fs_farmer,
                form=self.form,
            ).exists()
        )

    def test_multiple_syncs_idempotent(self):
        """Running sync multiple times doesn't
        create duplicate mappings."""
        self._initial_sync()

        content = _make_content(
            survey=[
                _text_field(
                    "farmer_name", "Farmer"
                ),
                _text_field(
                    "region_name", "Region"
                ),
                _text_field("phone", "Phone"),
            ]
        )

        # Sync 3 more times
        for _ in range(3):
            sync_form_questions(
                self.form, content
            )

        self.assertEqual(
            FieldMapping.objects.filter(
                form=self.form
            ).count(),
            2,
        )

    def test_other_form_mappings_unaffected(self):
        """Syncing one form doesn't affect
        another form's mappings."""
        self._initial_sync()

        other_form = FormMetadata.objects.create(
            asset_uid="otherForm",
            name="Other Form",
        )
        other_content = _make_content(
            survey=[
                _text_field("name", "Name"),
            ]
        )
        sync_form_questions(
            other_form, other_content
        )
        other_q = FormQuestion.objects.get(
            form=other_form, name="name"
        )
        FieldMapping.objects.create(
            field=self.fs_phone,
            form=other_form,
            form_question=other_q,
        )

        # Re-sync the first form
        content = _make_content(
            survey=[
                _text_field(
                    "farmer_name", "Farmer"
                ),
                _text_field(
                    "region_name", "Region"
                ),
                _text_field("phone", "Phone"),
            ]
        )
        sync_form_questions(self.form, content)

        # Other form's mapping untouched
        self.assertTrue(
            FieldMapping.objects.filter(
                form=other_form,
                field=self.fs_phone,
            ).exists()
        )
        # Original form still has its 2
        self.assertEqual(
            FieldMapping.objects.filter(
                form=self.form
            ).count(),
            2,
        )
