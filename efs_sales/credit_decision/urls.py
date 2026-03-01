from django.urls import path
from . import views

app_name = "credit_decision"

urlpatterns = [
    # UI endpoint(s)
    path("", views.index, name="index"),

    # API endpoint
    path("fetch_sales_override/<uuid:transaction_id>/", views.fetch_sales_override, name="fetch_sales_override"),
    path("receive/", views.receive_credit_settings, name="receive_credit_settings"),

]

