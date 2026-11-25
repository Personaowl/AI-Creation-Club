from django.urls import path

from . import views
from .models import Asset

urlpatterns = [
    path("works/", views.work_list),
    path("works/<uuid:work_id>/", views.work_detail),
    path("works/<uuid:work_id>/assets/", views.upload),
    path("works/<uuid:work_id>/assets/<uuid:asset_id>/", views.delete_asset),
    path("works/<uuid:work_id>/assets/<uuid:asset_id>/download/", views.download, name="asset_download"),
    path("works/<uuid:work_id>/assets/<uuid:asset_id>/video/", views.media, {"kind": Asset.Kind.VIDEO}),
    path("works/<uuid:work_id>/assets/<uuid:asset_id>/audio/", views.media, {"kind": Asset.Kind.AUDIO}, name="asset_audio"),
    path("works/<uuid:work_id>/assets/<uuid:asset_id>/pdf/<int:page>/", views.pdf_page, name="asset_pdf_page"),
    path("works/<uuid:work_id>/assets/<uuid:asset_id>/presentation/", views.presentation),
    path("works/<uuid:work_id>/assets/<uuid:asset_id>/viewer/", views.office_viewer, name="office_viewer"),
    path("works/<uuid:work_id>/submit/", views.submit),
    path("works/<uuid:work_id>/withdraw/", views.withdraw),
    path("manage/works/<uuid:work_id>/review/", views.review),
    path("manage/works/<uuid:work_id>/access/", views.access),
]
