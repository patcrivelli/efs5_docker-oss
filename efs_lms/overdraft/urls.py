from django.urls import path
from . import views

urlpatterns = [
    path("", views.overdraft_page, name="overdraft"),
]
