# efs_settings/urls.py  (project-level)
from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path('admin/', admin.site.urls),

    # Include all app-level routes (settings/, save-settings/, post-settings/, etc.)
    path('', include('core.urls')),
]
