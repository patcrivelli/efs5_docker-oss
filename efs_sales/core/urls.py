from django.urls import path
from . import views
from core import views as core_views


urlpatterns = [
    path("", views.sales_view, name="sales_home"),                 # existing
    path("sales/", views.sales_view, name="sales_home_sales"),     # NEW alias
    path("sales-home/", views.sales_home, name="sales_home"),





# Proxies for efs credit decision service 
    path("receive_application_data/", views.receive_application_data, name="receive_application_data"),
    path("fetch_credit_score_data/<str:abn>/", views.fetch_credit_score_data, name="fetch_credit_score_data"),
    path("fetch_credit_report/<str:abn>/<str:tx>/", views.fetch_credit_report, name="fetch_credit_report_slash"),
    path("fetch_sales_override/<str:tx>/",          views.fetch_sales_override, name="fetch_sales_override"),

    path("modal/apis", views.modal_apis, name="modal_apis"),
    path("modal/abn", views.modal_abn, name="modal_abn"),
    path("modal/credit-score", views.modal_credit_score, name="modal_credit_score"),
    path("modal/bank-statements", views.modal_bank_statements, name="modal_bank_statements"),
    path("modal/financials", views.modal_financials, name="modal_financials"),
    path("modal/ppsr", views.modal_ppsr, name="modal_ppsr"),
    path("modal/x-sell", views.modal_xsell, name="modal_xsell"),
    path("get_product_by_transaction_id/", views.get_product_by_transaction_id, name="get_product_by_transaction_id"),
    path("approve_application/", views.approve_application, name="approve_application"),
    path("modal/apis", views.modal_apis, name="modal_apis"),
    path("apis/orchestrate", views.apis_orchestrate, name="apis_orchestrate"),
    path("apis/fetch-bureau-data/", views.apis_fetch_bureau_data, name="apis_fetch_bureau_data"),
    path("apis/application-details", views.modal_application_details, name="modal_application_details"),
    path("modal/terms", views.modal_terms, name="modal_terms"),


    # 🔄 Bank statements: switch modal to BFF + add data endpoints
    path("modal/bank-statements", views.modal_bank_statements, name="core_modal_bank_statements"),
    path("display_bank_account_data/<str:abn>/", views.display_bank_account_data, name="core_display_bank_account_data"),
    path("bankstatements/summary/<str:abn>/", views.bankstatements_summary, name="core_bankstatements_summary"),
    path("sales/bankstatements/analyse-ai/<str:abn>/", views.proxy_bankstatements_analyse_ai, name="sales_bankstatements_analyse_ai"),
    path("financial/notes/save/", views.proxy_save_financial_notes, name="financial_notes_save"),




    path("modal/ppsr", views.proxy_ppsr_modal),               # accept both with/without trailing slash if you want
    path("modal/ppsr/", views.proxy_ppsr_modal),
    path("fetch_ppsr_data/<str:abn>/", views.proxy_ppsr_for_abn),
    path("modal/tasks", views.modal_tasks, name="modal_tasks"),  # BFF proxy



    # ✅ Terms modal + proxies (NEW)
    path("modal/terms", views.modal_terms, name="sales_modal_terms"),
    path("application/terms/fetch/", views.terms_fetch_proxy, name="sales_terms_fetch"),
    path("application/terms/save/",  views.terms_save_proxy,  name="sales_terms_save"),



  
# ---- Updated / Agents ----
    path("modal/tasks", views.modal_tasks, name="modal_tasks"),
    path("run-agent-analysis/", views.run_agent_analysis, name="run_agent_analysis"),
    path("financial_summary/<str:abn>/", views._guard_financial_summary_on_sales),

# ---- create a deal modal----

    path("modal/create-deal/", views.create_deal_modal, name="create_deal_modal"),
    path("create_deal/", views.create_deal, name="create_deal"),

# ---- create a link ----

    path("sales/abns/", views.abns_list_proxy, name="sales_abns_list"),
    path("acns/", views.acns_list_proxy, name="sales_acns"),  # NEW

    path("sales/link-entities/", views.link_entities_proxy, name="sales_link_entities"),
    path("linked-entities/", views.linked_entities_bff, name="sales_linked_entities"),

# ---- file uploads----

    path("upload-financials/", views.proxy_upload_financials, name="proxy_upload_financials"),
    path("upload-ar-ledger/", views.proxy_upload_ar_ledger, name="proxy_upload_ar_ledger"),
    path("upload-ap-ledger/", views.proxy_upload_ap_ledger, name="proxy_upload_ap_ledger"),
    path("upload-asset-schedule/", views.upload_asset_schedule_bff, name="upload_asset_schedule_bff"),
    path("sales/upload-plant-machinery-schedule/", views.upload_plant_machinery_schedule_bff),
    path("fetch_asset_schedule_rows/<str:abn>/", views.fetch_asset_schedule_rows_bff, name="fetch_asset_schedule_rows_bff"),
    path("sales/fetch_plant_machinery_schedule_rows/<str:abn>/", views.fetch_plant_machinery_schedule_rows_bff, name="sales_fetch_pm_rows",),
    path("fetch_statutory_obligations/<str:entity_id>/", views.proxy_fetch_statutory_obligations, name="proxy_fetch_statutory_obligations"),


    path('save_financial_notes/', views.save_financial_notes, name='save_financial_notes'),
    path("sales/save_nav_snapshot/", views.save_nav_snapshot, name="save_nav_snapshot"),
    path("sales/api/assets/summary/", views.assets_summary_bff, name="assets_summary_bff"),
    path("sales/api/nav/latest/", views.nav_latest_bff, name="nav_latest_bff"),
    path("save_liabilities_nav/", views.save_liabilities_nav_bff, name="save_liabilities_nav",),
    path("api/liabilities/latest/", views.liabilities_latest_bff, name="liabilities_latest_bff"),

    path("upload-ppsr-data/", views.upload_ppsr_data_bff, name="upload_ppsr_data_bff"),
    path("upload-bureau-data/", views.upload_bureau_data_bff, name="upload_bureau_data_bff"),
    path("upload-debtor-credit-report/", views.bff_upload_debtor_credit_report, name="bff_upload_debtor_credit_report"),
    path(
        "api/debtors/credit-report/state/",
        views.proxy_update_debtor_credit_report_state,
        name="proxy_update_debtor_credit_report_state",
    ),
    path("upload-invoices/", views.upload_invoices_proxy, name="upload_invoices_proxy"),
    path("fetch_invoices/<str:company_id>/", views.fetch_invoices_proxy, name="fetch_invoices_proxy"),
    path(
        "api/invoices/approve-reject/",
        views.invoice_approve_reject_bff,
        name="invoice_approve_reject_bff"
    ),
    

    # ✅ Payables (new)
    path("upload-ap-invoices/", views.upload_ap_invoices_proxy, name="upload_ap_invoices_proxy"),
    path("sales/fetch-ap-invoices/<str:company_id>/", views.fetch_ap_invoices_proxy, name="fetch_ap_invoices_proxy"),

    #tax
    path("upload-tax-document/", views.proxy_upload_tax_document, name="proxy_upload_tax_document"),

    path("run_financial_analysis/", views.run_financial_analysis, name="run_financial_analysis"),
    
    
    # this is theproxt for the code to generate the final report for investors
    path(
        "api/agents/generate-report/",
        views.agents_generate_report_proxy,
        name="generate_credit_report_proxy",   # <-- MATCH the template
    ),

    path("bff/applications/<str:tx>/delete/", views.bff_delete_application, name="bff_delete_application"),

# save agent reports to memoery in efs_agents code 
    path("sales/save-agent-memory/", views.sales_save_agent_memory, name="sales_save_agent_memory"),




]
