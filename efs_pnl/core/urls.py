from django.urls import path
from . import views

urlpatterns = [
    path("", views.pnl_home, name="home"),                  # /
    path("pnl/", views.pnl_view, name="pnl_home"),          # unified pnl view
    path("create-originator/", views.create_originator, name="create_originator"),
]
