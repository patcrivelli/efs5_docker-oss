# efs_data_financial/core/urls.py
from django.urls import path
from . import views

urlpatterns = [
    path("ping/", views.ping, name="ping"),
    path("receive-invoice-data/", views.receive_invoice_data, name="receive_invoice_data"),
    path("receive-ledger-data/", views.receive_ledger_data, name="receive_ledger_data"),
    
    path("api/financial/receive-tf-invoice-data/", views.receive_tf_invoice_data, name="receive_tf_invoice_data_api"),
    path("api/financial/receive-scf-invoice-data/", views.receive_scf_invoice_data),

    
    path("modal/financials/", views.financials_modal, name="financials_modal"),
    path("api/financials/store/", views.store_financials, name="store_financials"),
    path("api/ppsr/store/", views.store_ppsr_data, name="store_ppsr_data"),
    path("fetch_financial_data/<str:abn>/", views.fetch_financial_data, name="fetch_financial_data"),
    path("fetch_invoices/<str:abn>/", views.fetch_invoices, name="fetch_invoices"),


#end point for bankstatements sales notes --> financial statement notes data model
    path("api/financial-statement-notes/save/", views.save_financial_statement_notes),



    # ✅ NEW:
    path("modal/ppsr/", views.ppsr_modal, name="ppsr_modal"),
    path("api/ppsr/<str:abn>/", views.ppsr_for_abn, name="ppsr_for_abn"),



    path("list-models/", views.list_models, name="list_models"),
    path("financial/full/<str:abn>/", views.financial_full, name="financial_full"),
    path("financial/full_tx/<str:tx>/", views.financial_full_tx, name="financial_full_tx"),


    path("ppsr/<str:abn>/", views.ppsr_for_abn_summary, name="ppsr_for_abn_summary"),
    path("ppsr/raw/<str:abn>/", views.ppsr_for_abn, name="ppsr_for_abn"), 
    path("ppsr/full_tx/<str:tx>/", views.ppsr_full_tx, name="ppsr_full_tx"),
    #path("api/ppsr_abn/<str:abn>/", views.ppsr_api_for_abn_strict, name="ppsr_api_for_abn_strict"),



    path("upload-financials/", views.upload_financials, name="upload_financials"),
    path("upload-ar-ledger/", views.upload_ar_ledger, name="upload_ar_ledger"),
    path("upload-ap-ledger/", views.upload_ap_ledger, name="upload_ap_ledger"),
    path("upload-asset-schedule/", views.upload_asset_schedule, name="upload_asset_schedule"),
    path("upload-plant-machinery-schedule/", views.upload_plant_machinery_schedule, name="upload_plant_machinery_schedule",),
    path("upload-debtor-credit-report-pdf/", views.upload_debtor_credit_report_pdf, name="upload_debtor_credit_report_pdf"),

    path(
        "api/debtors/credit-report/state/",
        views.update_debtor_credit_report_state,
        name="update_debtor_credit_report_state"
    ),
    path("api/invoices/upload-csv/", views.upload_invoices_csv, name="upload_invoices_csv"),
    path("api/invoices/fetch/<str:company_id>/", views.fetch_invoices_combined, name="fetch_invoices_combined"),
    path("api/invoices/approve-reject/", views.update_invoice_approve_reject, name="update_invoice_approve_reject"),


    path("api/invoices/upload-ap-csv/", views.upload_ap_invoices_csv, name="upload_ap_invoices_csv"),
    path("api/invoices/ap/fetch/<str:company_id>/", views.fetch_ap_invoices_combined, name="fetch_ap_invoices_combined"),




    #tax
    path("upload-tax-document/", views.upload_tax_document, name="upload_tax_document"),



    path('save-financial-notes/', views.save_financial_notes, name='save_financial_notes'),
    path('fetch_financial_sections_pivot/<str:abn>/', views.fetch_financial_sections_pivot, name='fetch_financial_sections_pivot'),
    path("fetch_accounts_payable/<str:abn>/", views.fetch_accounts_payable, name="fetch_accounts_payable"),
    path("fetch_asset_schedule_rows/<str:abn>/", views.fetch_asset_schedule_rows),
    path("fetch_plant_machinery_schedule_rows/<str:abn>/", views.fetch_plant_machinery_schedule_rows, name="fetch_plant_machinery_schedule_rows",),
    path("api/liabilities/latest/", views.liabilities_latest, name="liabilities_latest",),
    path("fetch_statutory_obligations/<str:entity_id>/", views.fetch_statutory_obligations, name="fetch_statutory_obligations"),



    path("apis/upload-ppsr-data/", views.upload_ppsr_data_view, name="upload_ppsr_data"),

    path("save_nav_snapshot/", views.save_nav_snapshot, name="save_nav_snapshot"),
    path("api/assets/summary/", views.assets_summary_api, name="assets_summary_api"),
    path("api/nav/latest/", views.nav_latest_api, name="nav_latest_api"),
    path("save_liabilities_nav/", views.save_liabilities_nav, name="save_liabilities_nav"),
    path("api/data-checklist-status/", views.data_checklist_status, name="data_checklist_status"),

    path("api/nav/ar/latest/<str:tx>/", views.nav_ar_latest_by_tx, name="nav_ar_latest_by_tx"),
    path("api/invoices/rejected-face-sum/<str:tx>/", views.rejected_invoices_face_value_sum, name="rejected_invoices_face_sum"),




# endpoint to send invoice data from efs_data_financial to efs_lms_invoice finance
    path("api/financial/invoices/", views.invoices_by_transaction, name="invoices_by_transaction"),



# RAG endpoints to send data models to RAG generation.html 
    path("api/model-list/", views.model_list_api, name="model_list_api"),
    path("api/model-metadata/", views.model_metadata_api, name="model_metadata_api"),


    path("run_financial_analysis/", views.run_financial_analysis, name="run_financial_analysis"),
    path(
        "api/debtors-credit-reports/by-transaction/",
        views.debtor_credit_reports_by_transaction,
        name="debtor_credit_reports_by_transaction",
    ),



    path("api/purge/<tx>/",     views.purge_by_tx,     name="edf_purge_by_tx"),
    path("api/nav/purge/<tx>/", views.nav_purge_by_tx, name="edf_nav_purge_by_tx"),



    path(
        "api/financial-data/upsert-json/",
        views.upsert_financial_json,
        name="upsert_financial_json",
    ),



    path("api/ledger-data/bulk-upload/", views.bulk_upload_ar_ledger, name="bulk_upload_ar_ledger"),
    path("api/ap-ledger-data/bulk-upload/", views.bulk_upload_ap_ledger, name="bulk_upload_ap_ledger"),


]