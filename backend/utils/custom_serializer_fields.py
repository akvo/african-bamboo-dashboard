from django.core.validators import EmailValidator
from django.utils.translation import gettext_lazy as _
from rest_framework.fields import (BooleanField, CharField, ChoiceField,
                                   DateField, DateTimeField, DecimalField,
                                   Field, FileField, FloatField, ImageField,
                                   IntegerField, JSONField, ListField,
                                   MultipleChoiceField, URLField)
from rest_framework.relations import PrimaryKeyRelatedField

key_map = {}


class CustomIntegerField(IntegerField):
    default_error_messages = {
        "invalid": _("A valid field_title is required."),
        "max_value": _(
            "Ensure field_title is less than or equal to {max_value}."
        ),
        "min_value": _(
            "Ensure field_title is greater than or equal to {min_value}."
        ),
        "max_string_length": _("field_title value too large."),
        "required": _("field_title is required."),
        "null": _("field_title may not be null."),
    }


class CustomCharField(CharField):
    default_error_messages = {
        "invalid": _("A valid field_title is required."),
        "blank": _("field_title may not be blank."),
        "max_length": _(
            "Ensure field_title has no more than {max_length} characters."
        ),
        "min_length": _(
            "Ensure field_title has at least {min_length} characters."
        ),
        "required": _("field_title is required."),
        "null": _("field_title may not be null."),
    }


class CustomChoiceField(ChoiceField):
    default_error_messages = {
        "invalid_choice": _('"{input}" is not a valid choice in field_title.'),
        "required": _("field_title is required."),
        "null": _("field_title may not be null."),
    }


class CustomMultipleChoiceField(MultipleChoiceField):
    default_error_messages = {
        "invalid_choice": _('"{input}" is not a valid choice in field_title.'),
        "not_a_list": _(
            'Expected a list of items but got type "{input_type}"'
            " in field_title."
        ),
        "empty": _("This selection may not be empty in field_title."),
    }


class CustomImageField(ImageField):
    default_error_messages = {
        "invalid_image": _(
            "Upload a valid image. field_title you uploaded was either not "
            "an image or a corrupted image."
        ),
        "required": _("field_title is required."),
        "null": _("field_title may not be null."),
    }


class CustomEmailField(CustomCharField):
    default_error_messages = {"invalid": _("Enter a valid email address.")}

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        validator = EmailValidator(message=self.error_messages["invalid"])
        self.validators.append(validator)


class CustomListField(ListField):
    default_error_messages = {
        "not_a_list": _(
            "Expected a list of items in field_title but got type"
            ' "{input_type}".'
        ),
        "empty": _("field_title may not be empty."),
        "min_length": _(
            "Ensure field_title has at least {min_length} elements."
        ),
        "max_length": _(
            "Ensure field_title has no more than {max_length} elements."
        ),
        "required": _("field_title is required."),
        "null": _("field_title may not be null."),
    }


class CustomBooleanField(BooleanField):
    default_error_messages = {
        "invalid": _("Must be a valid field_title."),
        "required": _("field_title is required."),
        "null": _("field_title may not be null."),
    }


class CustomFloatField(FloatField):
    default_error_messages = {
        "invalid": _("A valid field_title is required."),
        "max_value": _(
            "Ensure field_title is less than or equal to {max_value}."
        ),
        "min_value": _(
            "Ensure field_title is greater than or equal to {min_value}."
        ),
        "max_string_length": _("field_title too large."),
        "required": _("field_title is required."),
        "null": _("field_title may not be null."),
    }


class CustomDecimalField(DecimalField):
    default_error_messages = {
        "invalid": _("A field_title number is required."),
        "max_value": _(
            "Ensure field_title is less than or equal to {max_value}."
        ),
        "min_value": _(
            "Ensure field_title is greater than or equal to {min_value}."
        ),
        "max_digits": _(
            "Ensure that in field_title are no more than {max_digits} "
            "digits in total."
        ),
        "max_decimal_places": _(
            "Ensure that in field_title are no more than {max_decimal_places} "
            "decimal places."
        ),
        "max_whole_digits": _(
            "Ensure that in field_title are no more than {max_whole_digits} "
            "digits before the "
            "decimal point."
        ),
        "max_string_length": _("String value too large in field_title."),
        "required": _("field_title is required."),
        "null": _("field_title may not be null."),
    }


class CustomURLField(URLField):
    default_error_messages = {
        "invalid": _("Enter a valid URL in field_title."),
        "required": _("field_title is required."),
        "null": _("field_title may not be null."),
    }


class CustomPrimaryKeyRelatedField(PrimaryKeyRelatedField):
    default_error_messages = {
        "required": _("field_title is required."),
        "does_not_exist": _('Invalid pk "{pk_value}" - object does not exist.'),
        "incorrect_type": _(
            "Incorrect type. Expected pk value, received {data_type}."
        ),
        "null": _("field_title may not be null."),
    }


class CustomDateField(DateField):
    default_error_messages = {
        "required": _("field_title is required."),
        "invalid": _(
            "Date has wrong format. Use one of these formats instead:"
            " {format}."
        ),
        "datetime": _("Expected a date but got a datetime."),
        "null": _("field_title may not be null."),
    }


class CustomFileField(FileField):
    default_error_messages = {
        "required": _("No file was submitted in field_title."),
        "invalid": _(
            "The submitted data was not a file. Check the encoding type on the"
            " form in field_title."
        ),
        "no_name": _("No filename could be determined in field_title."),
        "empty": _("The submitted file is empty in field_title."),
        "max_length": _(
            "Ensure this filename has at most {max_length} characters"
            " (it has {length}) in field_title."
        ),
    }


class CustomDateTimeField(DateTimeField):
    default_error_messages = {
        "invalid": _(
            "Datetime has wrong format. Use one of these formats instead: "
            "{format} in field_title."
        ),
        "date": _("field_title Expected a datetime but got a date."),
        "make_aware": _(
            'Invalid datetime for the timezone "{timezone} in field_title".'
        ),
        "overflow": _("Datetime value out of range in field_title."),
    }


class CustomUrlField(URLField):
    default_error_messages = {"invalid": _("Enter a valid URL.")}


class CustomJSONField(JSONField):
    default_error_messages = {
        "invalid": _("Value must be valid JSON in field_title."),
        "required": _("field_title field is required"),
    }


class UnvalidatedField(Field):
    default_error_messages = {
        "null": _("field_title may not be null."),
    }

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.allow_blank = True
        self.allow_null = False

    def to_internal_value(self, data):
        return data

    def to_representation(self, value):
        return value


def _collect_errors(data, messages, field_name=None):
    if isinstance(data, dict):
        for key, value in data.items():
            _collect_errors(value, messages, field_name=key)
    elif isinstance(data, list):
        for item in data:
            _collect_errors(item, messages, field_name=field_name)
    elif isinstance(data, str):
        name = str(field_name) if field_name is not None else ""
        label = key_map.get(name, name)
        messages.append(data.replace("field_title", label))


def validate_serializers_message(errors):
    messages = []
    _collect_errors(errors, messages)
    return "|".join(messages)
