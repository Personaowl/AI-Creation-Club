from django.shortcuts import redirect
from django.urls import include, path, re_path
from django.views.decorators.http import require_safe

from works.office import office_source


@require_safe
def management_redirect(request):
    path_info = request.path_info
    section = "/accounts" if path_info.startswith("/admin/auth/user/") else ""
    if path_info.startswith("/admin/works/"):
        section = "/works"
    return redirect(f"/#manage{section}")


urlpatterns = [
    re_path(r"^admin(?:/.*)?$", management_redirect),
    path("api/auth/", include("accounts.urls")),
    path("api/", include("works.urls")),
    path("internal/office/source/<uuid:asset_id>/", office_source, name="office_source"),
]
