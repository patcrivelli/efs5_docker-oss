from django.urls import path
from . import views

app_name = "scf"  # ✅ namespacing

urlpatterns = [
    path("", views.scf_page, name="scf_page"),      # main page
    path("api/ping/", views.ping, name="ping"),     # healthcheck
]
