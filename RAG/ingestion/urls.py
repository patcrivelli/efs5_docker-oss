from django.urls import path
from . import views

urlpatterns = [
    path("", views.ingestion_home, name="ingestion_home"),  # this catches http://localhost:8029/
    path("create-originator/", views.create_originator, name="create_originator"),


    path("upload/", views.upload_document, name="ingestion_upload"),

]
