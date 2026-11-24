from django import forms
from django.contrib import admin
from django.urls import reverse
from django.utils.html import format_html

from .models import AccessChange, Asset, Review, Work
from .services import change_access, review_work


class WorkReviewForm(forms.ModelForm):
    decision = forms.ChoiceField(
        label="审核操作",
        choices=[("", "保留现状"), (Work.Status.APPROVED, "通过"), (Work.Status.REJECTED, "退回")],
        required=False,
    )
    note = forms.CharField(label="本次审核意见", max_length=1000, required=False, widget=forms.Textarea(attrs={"rows": 3}))

    class Meta:
        model = Work
        fields = ("is_visible", "allow_download")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        pending = self.instance.status == Work.Status.PENDING
        approved = self.instance.status == Work.Status.APPROVED
        for name in ("decision", "note"):
            self.fields[name].disabled = not pending
        for name in ("is_visible", "allow_download"):
            self.fields[name].disabled = not approved

    def clean(self):
        data = super().clean()
        if data.get("decision") == Work.Status.REJECTED and not data.get("note"):
            self.add_error("note", "退回时请填写原因。")
        return data


class AssetInline(admin.TabularInline):
    model = Asset
    extra = 0
    fields = ("original_name", "kind", "size", "inspect_asset")
    readonly_fields = fields
    can_delete = False

    def has_add_permission(self, request, obj):
        return False

    @admin.display(description="检查附件")
    def inspect_asset(self, asset):
        args = [asset.work_id, asset.pk]
        original = reverse("asset_download", args=args)
        if asset.kind == Asset.Kind.SLIDES:
            return format_html('<a href="{}">在线浏览 PPT</a> · <a href="{}">下载原件</a>', reverse("office_viewer", args=args), original)
        return format_html('<a href="{}">下载原件</a>', original)


class ReviewInline(admin.TabularInline):
    model = Review
    extra = 0
    fields = ("reviewer", "decision", "note", "created_at")
    readonly_fields = fields
    can_delete = False

    def has_add_permission(self, request, obj):
        return False


class AccessChangeInline(admin.TabularInline):
    model = AccessChange
    extra = 0
    fields = ("actor", "is_visible", "allow_download", "created_at")
    readonly_fields = fields
    can_delete = False

    def has_add_permission(self, request, obj):
        return False


@admin.register(Work)
class WorkAdmin(admin.ModelAdmin):
    form = WorkReviewForm
    list_display = ("title", "display_owner", "status", "is_visible", "allow_download", "updated_at")
    list_filter = ("status", "is_visible", "allow_download")
    search_fields = ("title", "owner__username")
    list_select_related = ("owner",)
    readonly_fields = ("title", "owner", "description", "status", "review_note", "created_at", "updated_at")
    fieldsets = (
        ("作品信息", {"fields": readonly_fields}),
        ("审核", {"fields": ("decision", "note")}),
        ("已通过作品权限", {"fields": ("is_visible", "allow_download")}),
    )
    inlines = (AssetInline, ReviewInline, AccessChangeInline)

    @admin.display(description="作者", ordering="owner")
    def display_owner(self, obj):
        return obj.owner

    def changelist_view(self, request, extra_context=None):
        return super().changelist_view(request, {"title": "竞赛作品", **(extra_context or {})})

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def save_model(self, request, obj, form, change):
        data = form.cleaned_data
        if data["decision"]:
            review_work(request.user, obj.pk, data["decision"], data["note"])
        elif obj.status == Work.Status.APPROVED:
            change_access(request.user, obj.pk, is_visible=data["is_visible"], allow_download=data["allow_download"])
        obj.refresh_from_db()
