from django.urls import path
from .views import OriginatorList, OriginatorCreate, profile_home, create_originator

urlpatterns = [
    path("", profile_home, name="profile_page"),  
    path("create-originator/", create_originator, name="create_originator"),

    path("api/originators/", OriginatorList.as_view(), name="originator_list"),
    path("api/originators/create/", OriginatorCreate.as_view(), name="originator_create"),
]
