from django.urls import path

from . import views

urlpatterns = [
    path("works/", views.work_list),
    path("works/<uuid:work_id>/", views.work_detail),
    path("works/<uuid:work_id>/assets/", views.upload),
    path("works/<uuid:work_id>/assets/<uuid:asset_id>/", views.delete_asset),
    path("works/<uuid:work_id>/assets/<uuid:asset_id>/download/", views.download, name="asset_download"),
    path("works/<uuid:work_id>/assets/<uuid:asset_id>/video/", views.video),
    path("works/<uuid:work_id>/assets/<uuid:asset_id>/presentation/", views.presentation),
    path("works/<uuid:work_id>/assets/<uuid:asset_id>/viewer/", views.office_viewer, name="office_viewer"),
    path("works/<uuid:work_id>/submit/", views.submit),
    path("manage/works/<uuid:work_id>/review/", views.review),
    path("manage/works/<uuid:work_id>/access/", views.access),
]
