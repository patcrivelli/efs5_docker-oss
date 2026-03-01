from django.urls import path
from django.views.generic import TemplateView
app_name = "term_loan"
urlpatterns = [ path("", TemplateView.as_view(template_name="term_loan.html"), name="index") ]
