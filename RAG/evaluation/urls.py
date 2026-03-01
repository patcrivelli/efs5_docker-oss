from django.urls import path
from . import views

urlpatterns = [
    path("", views.evaluation_home, name="evaluation_home"),
    path("create-originator/", views.create_originator, name="create_originator"),
]
