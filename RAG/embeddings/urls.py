from django.urls import path
from . import views

urlpatterns = [
    path("", views.embeddings_home, name="embeddings_home"),
    path("create-originator/", views.create_originator, name="create_originator"),


    path("create/", views.create_embeddings, name="create_embeddings"),

]
