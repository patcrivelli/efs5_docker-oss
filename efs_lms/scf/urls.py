from django.urls import path
from . import views

urlpatterns = [
    path("", views.scf_page, name="scf"),
]
