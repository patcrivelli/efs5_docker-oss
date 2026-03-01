from django.urls import path
from django.views.generic import TemplateView
app_name = "asset_finance"
urlpatterns = [ path("", TemplateView.as_view(template_name="asset_finance.html"), name="index") ]
