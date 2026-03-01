from django.urls import path
from . import views

urlpatterns = [
    path("", views.drawdowns_board, name="drawdowns_board"),            # root → board
    path("drawdowns/", views.drawdowns_board, name="drawdowns"),        # /drawdowns/ → board too
    path("create-originator/", views.create_originator, name="create_originator"),
    path("api/drawdowns/receive/", views.receive_drawdown, name="receive_drawdown"),

# ------Drawdown fetch compliance checks urls------
    path("drawdown-decision/fetch_credit_settings/", views.dd_fetch_settings),
    path("drawdown-decision/fetch_credit_score_data/<str:abn>/", views.dd_fetch_score),
    path("drawdown-decision/fetch_credit_report/<str:abn>/<str:tx>", views.dd_fetch_bureau_report),
    path("drawdown-decision/fetch_sales_override/<str:tx>/", views.dd_fetch_sales_override),


# ------Drawdown approval urls------

    path("drawdown-decision/approve/", views.dd_approve, name="dd_approve"),

]