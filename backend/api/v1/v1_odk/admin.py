from django.contrib import admin

from api.v1.v1_odk.models import (
    FieldMapping,
    FieldSettings,
    FormMetadata,
    FormOption,
    FormQuestion,
    MainPlot,
    MainPlotSubmission,
    Plot,
    Submission,
)

admin.site.register(FormMetadata)
admin.site.register(Submission)
admin.site.register(Plot)
admin.site.register(FormQuestion)
admin.site.register(FormOption)
admin.site.register(FieldSettings)
admin.site.register(FieldMapping)
admin.site.register(MainPlot)
admin.site.register(MainPlotSubmission)
