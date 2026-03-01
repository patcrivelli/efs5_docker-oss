from django.urls import path
from . import views



urlpatterns = [
    path("", views.retrieval_home, name="retrieval_home"),
    path("create-originator/", views.create_originator, name="create_originator"),

    path("test/", views.test_retrieval, name="test_retrieval"),
    
    path("save-retrieval/", views.save_retrieval, name="save_retrieval"),

]
