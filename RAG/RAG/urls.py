from django.contrib import admin
from django.urls import path, include
from django.shortcuts import redirect
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path("admin/", admin.site.urls),

    # Root → ingestion
    path("", lambda request: redirect("ingestion/")),

    # RAG apps
    path("ingestion/", include("ingestion.urls")),
    path("chunking/", include("chunking.urls")),
    path("embeddings/", include("embeddings.urls")),
    path("retrieval/", include("retrieval.urls")),
    path("generation/", include("generation.urls")),
    path("evaluation/", include("evaluation.urls")),


] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
