# application_data/urls.py
from django.urls import path
from . import views

urlpatterns = [
    path("receive-application-data/", views.receive_application_data, name="receive_application_data"),
    path("list/", views.ApplicationListView.as_view(), name="application_list"),
]
