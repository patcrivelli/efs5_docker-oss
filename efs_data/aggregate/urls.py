# aggregate/urls.py
from django.urls import path
from . import views

app_name = "aggregate"

urlpatterns = [
    path("ping/", views.ping, name="aggregate_ping"),
    path("", views.aggregate_page, name="aggregate_page"),

]
