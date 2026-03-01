

# efs_data_bureau/urls.py
from django.contrib import admin
from django.urls import path, include
from core.views import receive_products, receive_credit_decision  # adjust path if needed

urlpatterns = [
    path('admin/', admin.site.urls),
    path("", include("core.urls")),  # mount your app urls at root
    path('api/settings/products/receive/', receive_products, name='receive_products'),
    path("api/settings/credit-decision/receive/", receive_credit_decision, name="receive_credit_decision"),

]