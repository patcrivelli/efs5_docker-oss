# users/urls.py
from django.urls import path
from . import views

urlpatterns = [
    path("ajax-signup/", views.ajax_signup, name="ajax_signup"),
    path("ajax-login/", views.ajax_login, name="ajax_login"),

]
