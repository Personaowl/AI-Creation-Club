from django.contrib import admin
from django.urls import include, path

from works.office import office_source

admin.site.site_title = "AI Creation Club 作品平台"
admin.site.site_header = f"{admin.site.site_title} · 管理后台"
admin.site.index_title = "账号和作品审核"

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/auth/", include("accounts.urls")),
    path("api/", include("works.urls")),
    path("internal/office/source/<uuid:asset_id>/", office_source, name="office_source"),
]
