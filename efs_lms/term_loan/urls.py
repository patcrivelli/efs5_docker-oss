from django.urls import path
from . import views

urlpatterns = [
    path("", views.term_loan_page, name="term_loan"),
]