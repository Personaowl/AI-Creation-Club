from django.contrib import admin, messages
from django.contrib.auth import get_user_model
from django.contrib.auth.admin import UserAdmin
from django.utils.translation import gettext_lazy as _

from .services import reclaim_member

User = get_user_model()
admin.site.unregister(User)


@admin.register(User)
class EntryStageUserAdmin(UserAdmin):
    fieldsets = (
        (None, {"fields": ("username", "password")}),
        ("账号状态", {"fields": ("is_active", "is_superuser", "last_login", "date_joined")}),
    )
    readonly_fields = ("is_active", "is_superuser", "last_login", "date_joined")
    list_display = ("username", "is_active", "is_superuser", "last_login")
    list_filter = ("is_active", "is_superuser")
    search_fields = ("username",)
    actions = ["reclaim_accounts", "reactivate_accounts"]

    def has_delete_permission(self, request, obj=None):
        return False

    @admin.action(description=_("回收选中的普通账号"))
    def reclaim_accounts(self, request, queryset):
        count = 0
        for user in queryset.filter(is_staff=False, is_superuser=False):
            reclaim_member(user)
            count += 1
        self.message_user(request, f"已回收 {count} 个普通账号。", messages.SUCCESS)

    @admin.action(description=_("启用已重设密码的普通账号"))
    def reactivate_accounts(self, request, queryset):
        inactive = queryset.filter(is_active=False, is_staff=False, is_superuser=False)
        count = 0
        for user in inactive:
            if user.has_usable_password():
                count += User.objects.filter(pk=user.pk, is_active=False, password=user.password).update(is_active=True)
        self.message_user(request, f"已启用 {count} 个账号。回收后须先重设密码。", messages.SUCCESS)
