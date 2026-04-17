from django import forms
from django.contrib import admin, messages
from django.shortcuts import redirect, render
from django.urls import path

from api.v1.v1_users.constants import UserStatus
from api.v1.v1_users.models import SystemUser
from api.v1.v1_users.services import approval


class InviteUserForm(forms.Form):
    email = forms.EmailField()
    name = forms.CharField(required=False)
    kobo_url = forms.URLField(required=False)


@admin.register(SystemUser)
class SystemUserAdmin(admin.ModelAdmin):
    site_header = "Manage Users"

    list_display = (
        "email",
        "name",
        "kobo_username",
        "kobo_url",
        "status_label",
        "is_active",
        "status_changed_at",
        "last_login",
    )
    list_filter = ("status", "is_active", "is_superuser")
    search_fields = ("email", "name", "kobo_username")
    ordering = ("-status_changed_at",)
    readonly_fields = (
        "status_changed_at",
        "status_changed_by",
        "last_login",
        "invited_at",
    )
    fieldsets = (
        ("Identity", {"fields": ("email", "name")}),
        ("Kobo", {"fields": ("kobo_url", "kobo_username")}),
        (
            "Access",
            {
                "fields": (
                    "status",
                    "is_active",
                    "status_changed_at",
                    "status_changed_by",
                    "invited_at",
                )
            },
        ),
        ("Permissions", {"fields": ("is_superuser",)}),
    )
    actions = (
        "action_approve",
        "action_reject",
        "action_deactivate",
        "action_reactivate",
    )

    @admin.display(
        description="Status", ordering="status"
    )
    def status_label(self, obj):
        return UserStatus.fieldStr.get(obj.status, "?")

    def has_module_permission(self, request):
        return bool(
            request.user.is_authenticated
            and request.user.is_superuser
        )

    def get_urls(self):
        urls = super().get_urls()
        custom = [
            path(
                "invite/",
                self.admin_site.admin_view(
                    self.invite_view
                ),
                name="v1_users_systemuser_invite",
            ),
        ]
        return custom + urls

    def add_view(
        self, request, form_url="", extra_context=None
    ):
        return redirect(
            "admin:v1_users_systemuser_invite"
        )

    def invite_view(self, request):
        if not request.user.is_superuser:
            messages.error(request, "Permission denied.")
            return redirect(
                "admin:v1_users_systemuser_changelist"
            )
        if request.method == "POST":
            form = InviteUserForm(request.POST)
            if form.is_valid():
                try:
                    approval.create_invite(
                        email=form.cleaned_data["email"],
                        name=(
                            form.cleaned_data.get("name")
                            or None
                        ),
                        kobo_url=(
                            form.cleaned_data.get(
                                "kobo_url"
                            )
                            or None
                        ),
                        invited_by=request.user,
                    )
                except ValueError as exc:
                    messages.error(request, str(exc))
                else:
                    messages.success(
                        request, "Invitation sent."
                    )
                    return redirect(
                        "admin:"
                        "v1_users_systemuser_changelist"
                    )
        else:
            form = InviteUserForm()
        context = {
            **self.admin_site.each_context(request),
            "form": form,
            "title": "Invite user",
            "opts": self.model._meta,
        }
        return render(
            request,
            "admin/v1_users/invite_user.html",
            context,
        )

    def _bulk_action(
        self,
        request,
        queryset,
        *,
        allowed_from,
        fn,
        label,
    ):
        ok, skipped = 0, 0
        for user in queryset:
            if user.status not in allowed_from:
                skipped += 1
                continue
            fn(user, by=request.user)
            ok += 1
        if ok:
            messages.success(
                request, f"{label} {ok} user(s)."
            )
        if skipped:
            messages.warning(
                request,
                (
                    f"Skipped {skipped} user(s) not "
                    f"eligible for {label}."
                ),
            )

    @admin.action(
        description="Approve selected pending users"
    )
    def action_approve(self, request, queryset):
        self._bulk_action(
            request,
            queryset,
            allowed_from={UserStatus.PENDING},
            fn=approval.approve,
            label="Approved",
        )

    @admin.action(
        description="Reject selected pending users"
    )
    def action_reject(self, request, queryset):
        self._bulk_action(
            request,
            queryset,
            allowed_from={UserStatus.PENDING},
            fn=approval.reject,
            label="Rejected",
        )

    @admin.action(
        description="Deactivate selected active users"
    )
    def action_deactivate(self, request, queryset):
        self._bulk_action(
            request,
            queryset,
            allowed_from={UserStatus.ACTIVE},
            fn=approval.deactivate,
            label="Deactivated",
        )

    @admin.action(
        description="Reactivate selected suspended users"
    )
    def action_reactivate(self, request, queryset):
        self._bulk_action(
            request,
            queryset,
            allowed_from={UserStatus.SUSPENDED},
            fn=approval.reactivate,
            label="Reactivated",
        )
