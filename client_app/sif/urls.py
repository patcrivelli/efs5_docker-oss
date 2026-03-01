from django.urls import path
from django.views.generic import TemplateView
app_name = "sif"
urlpatterns = [ path("", TemplateView.as_view(template_name="sif.html"), name="index") ]
