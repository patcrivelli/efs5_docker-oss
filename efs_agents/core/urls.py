from django.urls import path
from . import views

app_name = "efs_agents"

urlpatterns = [
    path("agents/", views.agents_view, name="agents_home"),
    path("create-originator/", views.create_originator, name="create_originator"),
        # New stubs
    path("save-agent/", views.save_agent, name="save_agent"),
    path("placeholder-save-memory-config", views.save_memory_config, name="save_memory_config"),
    path("placeholder-assign-memory", views.assign_memory, name="assign_memory"),
    path("agent-archive/", views.agent_archive, name="agent_archive"),
    path("memory-audit/", views.memory_audit, name="memory_audit"),


    path("modal/sales-agents/", views.sales_agents_modal, name="agents_sales_agents_modal"),
    path("api/agents/by-name/", views.agent_by_name, name="agents_by_name"),
    path("api/agents/run/", views.run_agent_analysis, name="agents_run"),

    path("run-agent-analysis/", views.run_agent_analysis, name="run_agent_analysis"),

    
    #path("financials/by-abn/<str:abn>/", views.financials_by_abn_latest, name="financials_by_abn_latest"),
    path("sales/run-agent-analysis/", views.run_agent_analysis, name="sales_run_agent_analysis"),
    path("api/financial/summary/<str:abn>/", views.financial_summary_proxy),
    
# ---- this is the code to generate the final report for investors-----
    path("api/agents/generate-report/", views.generate_credit_report, name="agents_generate_report"),

# ---- save agent report in vector DB 
    path("api/agents/memory/save/", views.api_agents_memory_save, name="api_agents_memory_save"),




#efs_risk


    path("modal/risk-agents/", views.risk_agents_modal, name="risk_agents_modal"),

#efs_operations

    path("modal/operations-agents/", views.operations_agents_modal, name="operations_agents_modal"),

#efs_operations

    path("modal/finance-agents/", views.finance_agents_modal, name="finance_agents_modal"),


]
