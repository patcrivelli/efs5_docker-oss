# efs_risk/core/urls.py
from django.urls import path
from .views import risk_view, approve_transaction, credit_report, modal_risk_agents

urlpatterns = [
    path("", risk_view, name="risk_home"),                 # /
    path("risk/", risk_view, name="risk_home_alias"),      # /risk/
    path("api/approve_transaction/", approve_transaction, name="approve_transaction"),
    path("api/credit-report", credit_report, name="credit_report"),

    path("risk/modal/tasks/", modal_risk_agents, name="modal_risk_agents"),

]
