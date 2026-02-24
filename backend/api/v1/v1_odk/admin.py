from django.contrib import admin

from api.v1.v1_odk.models import (FormMetadata, FormOption, FormQuestion, Plot,
                                  Submission)

admin.site.register(FormMetadata)
admin.site.register(Submission)
admin.site.register(Plot)
admin.site.register(FormQuestion)
admin.site.register(FormOption)
