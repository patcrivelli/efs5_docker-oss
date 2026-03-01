# efs_credit_decision/core/urls.py
from django.urls import path
from . import views

app_name = "credit_decision"

urlpatterns = [
    # ---------- Canonical routes (preferred) ----------
    path("credit-decision/modal", views.cd_modal, name="cd_modal"),

    path("credit-decision/fetch_credit_settings/", views.cd_fetch_settings, name="cd_fetch_settings"),

    # Report: support both with and without trailing slash
    path("credit-decision/fetch_credit_report/<str:abn>/<str:tx>", views.cd_fetch_bureau_report, name="cd_fetch_bureau_report"),
    path("credit-decision/fetch_credit_report/<str:abn>/<str:tx>/", views.cd_fetch_bureau_report, name="cd_fetch_bureau_report_slash"),

    path("credit-decision/fetch_credit_score_data/<str:abn>/", views.cd_fetch_score, name="cd_fetch_score"),
    path("credit-decision/fetch_sales_override/<str:tx>/", views.cd_fetch_sales_override, name="cd_fetch_sales_override"),

    # Settings ingestion from efs_settings
    path("credit-decision/receive_credit_decision", views.cd_receive_settings, name="cd_receive_settings"),

    # ---------- Backward compatibility (legacy paths) ----------
    # These mirror older routes your frontend/proxies may still call.
    # Keep them until all callers migrate to the canonical ones above.
    path("modal/", views.cd_modal, name="modal_legacy"),
    path("fetch_credit_settings/", views.cd_fetch_settings, name="fetch_credit_settings_legacy"),
    path("fetch_credit_score_data/<str:abn>/", views.cd_fetch_score, name="fetch_credit_score_data_legacy"),
    path("fetch_credit_report/<str:abn>/<str:tx>/", views.cd_fetch_bureau_report, name="fetch_credit_report_legacy"),
    path("fetch_sales_override/<str:tx>/", views.cd_fetch_sales_override, name="fetch_sales_override_legacy"),
    path("api/settings/credit-decision/receive/", views.cd_receive_settings, name="receive_credit_decision_legacy"),
]
