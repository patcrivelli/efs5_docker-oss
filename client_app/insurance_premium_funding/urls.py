from django.urls import path
from django.views.generic import TemplateView
app_name = "insurance_premium_funding"
urlpatterns = [ path("", TemplateView.as_view(template_name="insurance_premium_funding.html"), name="index") ]
