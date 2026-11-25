from django.urls import path

from . import views

urlpatterns = [
    path("session/", views.session_view),
    path("login/", views.login_view),
    path("logout/", views.logout_view),
    path("password/", views.change_password),
    path("members/", views.members),
    path("members/<int:user_id>/reclaim/", views.reclaim),
    path("members/<int:user_id>/reissue/", views.reissue),
    path("members/<int:user_id>/reset-password/", views.reset_password),
]
