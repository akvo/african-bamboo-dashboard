from unittest.mock import patch

from django.test import TestCase

from utils.custom_serializer_fields import (
    UnvalidatedField,
    key_map,
    validate_serializers_message,
)


class UnvalidatedFieldTestCase(TestCase):
    def test_init_defaults(self):
        field = UnvalidatedField()
        self.assertTrue(field.allow_blank)
        self.assertFalse(field.allow_null)

    def test_to_internal_value_passes_through(self):
        field = UnvalidatedField()
        self.assertEqual(field.to_internal_value("hello"), "hello")
        self.assertEqual(field.to_internal_value(123), 123)
        self.assertEqual(
            field.to_internal_value({"a": 1}), {"a": 1}
        )

    def test_to_representation_passes_through(self):
        field = UnvalidatedField()
        self.assertEqual(field.to_representation("hello"), "hello")
        self.assertEqual(field.to_representation(42), 42)
        self.assertIsNone(field.to_representation(None))


class ValidateSerializersMessageTestCase(TestCase):
    """Example usage of validate_serializers_message.

    DRF validation errors come in various nested shapes
    depending on serializer structure (flat, nested, list).
    This function flattens them into a pipe-separated string
    and replaces 'field_title' with actual field names.
    """

    # --- Dict errors: flat fields ---

    def test_simple_field_error(self):
        # {"field": ["error message"]}
        errors = {"email": ["field_title is required."]}
        result = validate_serializers_message(errors)
        self.assertEqual(result, "email is required.")

    def test_multiple_field_errors(self):
        errors = {
            "email": ["field_title is required."],
            "name": ["field_title may not be blank."],
        }
        result = validate_serializers_message(errors)
        parts = result.split("|")
        self.assertIn("email is required.", parts)
        self.assertIn("name may not be blank.", parts)

    def test_multiple_errors_on_same_field(self):
        errors = {
            "password": [
                "field_title is required.",
                "field_title may not be blank.",
            ]
        }
        result = validate_serializers_message(errors)
        self.assertEqual(
            result,
            "password is required.|password may not be blank.",
        )

    # --- Dict errors: nested serializer ---

    def test_nested_serializer_errors(self):
        # Nested serializer: value is a dict, not a list
        # e.g. AddressSerializer inside UserSerializer
        errors = {
            "address": {
                "street": ["field_title is required."],
            }
        }
        result = validate_serializers_message(errors)
        self.assertEqual(result, "street is required.")

    def test_deeply_nested_serializer_errors(self):
        # e.g. CitySerializer inside AddressSerializer
        errors = {
            "address": {
                "city": {
                    "name": ["field_title is required."],
                }
            }
        }
        result = validate_serializers_message(errors)
        self.assertEqual(result, "name is required.")

    # --- Dict errors: list serializer items ---

    def test_list_serializer_item_errors(self):
        # ListSerializer: items are dicts with field errors
        errors = {
            "items": [
                {"name": ["field_title is required."]}
            ]
        }
        result = validate_serializers_message(errors)
        self.assertEqual(result, "name is required.")

    def test_list_serializer_deeply_nested(self):
        errors = {
            "items": [
                {
                    "details": [
                        {
                            "color": [
                                "field_title is required."
                            ]
                        }
                    ]
                }
            ]
        }
        result = validate_serializers_message(errors)
        self.assertEqual(result, "color is required.")

    # --- List errors (top-level) ---

    def test_top_level_list_with_dict_errors(self):
        errors = [{"name": ["field_title is required."]}]
        result = validate_serializers_message(errors)
        self.assertEqual(result, "name is required.")

    def test_top_level_list_with_nested_list(self):
        errors = [[{"key": ["field_title msg"]}]]
        result = validate_serializers_message(errors)
        self.assertEqual(result, "key msg")

    def test_top_level_list_with_nested_dict_value(self):
        errors = [
            {"profile": {"age": ["field_title is required."]}}
        ]
        result = validate_serializers_message(errors)
        self.assertEqual(result, "age is required.")

    # --- key_map usage ---

    @patch.dict(key_map, {"email": "Email Address"})
    def test_key_map_replaces_field_title(self):
        errors = {"email": ["field_title is required."]}
        result = validate_serializers_message(errors)
        self.assertEqual(result, "Email Address is required.")

    @patch.dict(key_map, {"street": "Street Name"})
    def test_key_map_in_nested_serializer(self):
        errors = {
            "address": {"street": ["field_title is required."]}
        }
        result = validate_serializers_message(errors)
        self.assertEqual(result, "Street Name is required.")

    # --- Edge cases ---

    def test_empty_dict(self):
        result = validate_serializers_message({})
        self.assertEqual(result, "")

    def test_empty_list(self):
        result = validate_serializers_message([])
        self.assertEqual(result, "")

    def test_no_field_title_placeholder(self):
        errors = {"email": ["Enter a valid email address."]}
        result = validate_serializers_message(errors)
        self.assertEqual(result, "Enter a valid email address.")

    def test_integer_key_in_nested(self):
        # DRF list errors use integer indices as keys
        errors = {0: ["field_title is required."]}
        result = validate_serializers_message(errors)
        self.assertEqual(result, "0 is required.")
