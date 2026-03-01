from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path("admin/", admin.site.urls),

    # Application data service
    path("api/application-data/", include("application_data.urls")),

    # Bureau service
    path("bureau/", include("bureau.urls")),

    # Financial data service
    path("api/financial/", include("financial.urls")),

    # Bank statements service
    path("bank_statements/", include("bank_statements.urls")),

    # Aggregates
    path("aggregate/", include("aggregate.urls")),
]

