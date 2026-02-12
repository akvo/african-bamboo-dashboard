from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from api.v1.v1_users.models import SystemUser


# Add manage users in admin django
class SystemUserAdmin(UserAdmin):
    site_header = "Manage Users"
    model = SystemUser
    list_display = (
        "email",
        "name",
        "email_verified",
    )
    list_filter = ("email_verified",)
    fieldsets = (
        (None, {"fields": ("email", "name", "password")}),
        (
            "Permissions",
            {"fields": ("email_verified",)},
        ),
    )
    add_fieldsets = (
        (
            None,
            {
                "classes": ("wide",),
                "fields": (
                    "email",
                    "name",
                    "password1",
                    "password2",
                ),
            },
        ),
    )
    search_fields = (
        "email",
        "name",
    )
    ordering = ("email",)

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        if not change:
            obj.generate_reset_password_code()


admin.site.register(SystemUser, SystemUserAdmin)
