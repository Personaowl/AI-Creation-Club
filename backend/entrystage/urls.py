from django.contrib import admin
from django.urls import include, path

from works.office import office_source

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/auth/", include("accounts.urls")),
    path("api/", include("works.urls")),
    path("internal/office/source/<uuid:asset_id>/", office_source, name="office_source"),
]
