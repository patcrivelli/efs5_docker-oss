# efs_data_bureau/core/urls.py
from django.urls import path
from . import views

app_name = "data_bureau"

urlpatterns = [
    # ---- Modals (local dev helpers)
    path("modal/abn", views.abn_modal),
    path("modal/abn/", views.abn_modal),

    path("modal/credit-score", views.credit_score_modal),
    path("modal/credit-score/", views.credit_score_modal),

    # ---- Credit score (UI demo + history)
    path("api/credit-score/<str:abn>", views.credit_score),
    path("api/credit-score/<str:abn>/", views.credit_score),

    path("api/credit-score-history/<str:abn>", views.credit_score_history),
    path("api/credit-score-history/<str:abn>/", views.credit_score_history),

    # ---- Credit report (legacy/demo endpoints)
    path("api/credit-report", views.credit_report, name="credit_report"),
    path("api/bureau/credit-report", views.credit_report),  # back-compat
    path("api/bureau/store-credit-report-data/", views.store_credit_report_data, name="store-credit-report-data"),

    # ---- Normalized report + settings used by the 8018 modal
    path("api/fetch_credit_report/<str:abn>/<str:tx>/", views.fetch_credit_report, name="fetch_credit_report"),
    path("api/fetch_credit_settings/", views.fetch_credit_settings, name="fetch_credit_settings"),
    path("api/fetch_override_history/<str:abn>/<str:tx>/", views.fetch_override_history, name="fetch_override_history"),
    path("api/save_ABN_modal/", views.save_abn_modal, name="save_ABN_modal"),

    # ---- Agents service helpers
    path("list-models/", views.list_models, name="list_models"),
    path("bureau/summary/<str:abn>/", views.bureau_summary, name="bureau_summary"),
    path("bureau/score/<str:abn>/", views.bureau_score, name="bureau_score"),
    path("bureau/score_history/<str:abn>/", views.bureau_score_history, name="bureau_score_history"),

    # ---- Upload parsing (PDF → DB)
    path("api/upload-credit-report-pdf/", views.upload_credit_report_pdf, name="upload_credit_report_pdf"),

    # ======================================================================
    # ====  CREDIT-DECISION-FACING ENDPOINTS (the ones your proxy calls) ===
    # ======================================================================

    # Non-API shape (what efs_credit_decision / sales BFF is calling)
    path("fetch_credit_report/<str:abn>/<str:tx>",  views.cd_bureau_fetch_credit_report, name="cd_bureau_fetch_credit_report"),
    path("fetch_credit_report/<str:abn>/<str:tx>/", views.cd_bureau_fetch_credit_report, name="cd_bureau_fetch_credit_report_slash"),

    path("fetch_credit_score_data/<str:abn>/", views.cd_bureau_fetch_credit_score, name="cd_bureau_fetch_credit_score"),

    # Optional: also expose the same under /api/ for flexibility
    path("api/fetch_credit_score_data/<str:abn>/", views.cd_bureau_fetch_credit_score, name="cd_bureau_fetch_credit_score_api"),
    path("api/fetch_credit_report/<str:abn>/<str:tx>",  views.cd_bureau_fetch_credit_report, name="cd_bureau_fetch_credit_report_api"),
    path("api/fetch_credit_report/<str:abn>/<str:tx>/", views.cd_bureau_fetch_credit_report, name="cd_bureau_fetch_credit_report_api_slash"),
    path("api/fetch_sales_override_current/<uuid:tx>/", views.fetch_sales_override_current),


]
