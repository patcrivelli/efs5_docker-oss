from django.urls import path
from . import views

urlpatterns = [
    path("", views.operations_home, name="home"),                        # /
    path("operations/", views.operations_view, name="operations"),       # ✅ unified operations view
    path("operations/home/", views.operations_home, name="operations_home"),  # optional landing page
    path("create-originator/", views.create_originator, name="create_originator"),

    path("operations/submit/", views.operations_submit, name="operations_submit"),
    path("modal/tasks/", views.modal_operations_agents, name="modal_operations_agents"),


]
