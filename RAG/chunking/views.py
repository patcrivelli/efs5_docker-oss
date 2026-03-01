import logging
import requests
from django.conf import settings
from django.shortcuts import render, redirect

logger = logging.getLogger(__name__)

# ---- helpers to talk to efs_profile ----
def _profile_base() -> str:
    return getattr(settings, "EFS_PROFILE_BASE_URL", "http://localhost:8002").rstrip("/")

def _api_key_header() -> dict:
    return {"X-API-Key": getattr(settings, "INTERNAL_API_KEY", "dev-key")}

def fetch_originators():
    try:
        r = requests.get(f"{_profile_base()}/api/originators/", timeout=5)
        r.raise_for_status()
        return r.json().get("originators", [])
    except Exception:
        logger.exception("Failed to fetch originators from efs_profile")
        return []

# ---- context used in templates ----
def base_context(request):
    originators = fetch_originators()
    selected_originator = None
    selected_id = request.GET.get("originators")
    if selected_id:
        for o in originators:
            if str(o.get("id")) == str(selected_id):
                selected_originator = o
                break
    return {
        "originators": originators,
        "selected_originator": selected_originator,
    }

# ---- pages ----
def chunking_home(request):
    ctx = base_context(request)
    ctx.update({"page_title": "RAG - Chunking"})
    return render(request, "chunking.html", ctx)

# ---- optional create handler ----
def create_originator(request):
    if request.method == "POST":
        payload = {
            "originator": request.POST.get("originator_name"),
            "created_by": request.POST.get("username"),
        }
        try:
            r = requests.post(
                f"{_profile_base()}/api/originators/create/",
                json=payload,
                headers=_api_key_header(),
                timeout=5,
            )
            if r.status_code not in (200, 201):
                logger.error("Originator create failed: %s %s", r.status_code, r.text)
        except Exception:
            logger.exception("Error calling efs_profile create originator")

    return redirect("chunking_home")

# -----------------
# Additional View Logic for Chunking Page
# -----------------
import logging
from typing import List, Dict

from django.shortcuts import render
from django.utils.text import Truncator

from chunking.models import ExtractionRun, Element
# Assuming these models are defined elsewhere and imported:
# from ingestion.models import DocumentFile, Document 
# from ingestion.views import base_context 

logger = logging.getLogger(__name__)


def chunking_home(request):
    """
    Renders the 'RAG - Chunking' page.

    Pulls recent ExtractionRuns and their Elements so we can see:
    - Which document/file they came from
    - Section metadata (section_title, weight, etc.)
    - The actual chunk text produced by the pipeline
    """

    # Get originators / selected_originator etc. so the header matches the rest of the app
    ctx = base_context(request)

    # 1. Fetch the most recent extraction runs
    # (Assuming ExtractionRun, DocumentFile, Document, and Element models are defined and imported)
    try:
        recent_runs = (
            ExtractionRun.objects
            .select_related("document_file", "document_file__document")
            .order_by("-created_at")[:5]
        )

        # 2. Collect run ids
        run_ids = [run.id for run in recent_runs]

        # 3. Fetch elements for those runs (text chunks only for now)
        elements_qs = (
            Element.objects
            .filter(extraction_id__in=run_ids, element_type="text")
            .select_related("extraction", "document", "extraction__document_file")
            .order_by("created_at")[:100]
        )

        # 4. Build table rows for the template
        chunk_rows: List[Dict] = []
        for el in elements_qs:
            run = el.extraction
            docfile = getattr(run, "document_file", None)
            doc = el.document

            # Safely access attributes (assuming DocumentFile and Document models)
            company_name = getattr(doc, "company_name", "—")
            fiscal_year = getattr(doc, "fiscal_year", "—")

            original_filename = getattr(docfile, "original_filename", "—") if docfile else "—"
            version = getattr(docfile, "version", "—") if docfile else "—"

            meta = el.meta or {}
            section_title = meta.get("section_title", "Body / Unknown Section")
            section_weight = meta.get("section_weight", 1.0)
            chunk_index = meta.get("chunk_index", 0)
            strategy = meta.get("strategy", meta.get("parser", "unknown"))

            preview_text = Truncator(el.text or "").chars(240)

            chunk_rows.append({
                "element_id": str(el.id),
                "company_name": company_name,
                "fiscal_year": fiscal_year,
                "original_filename": original_filename,
                "version": version,
                "section_title": section_title,
                "section_weight": section_weight,
                "chunk_index": chunk_index,
                "strategy": strategy,
                "preview_text": preview_text,
                "full_text": el.text or "",
                "created_at": el.created_at,
            })

        # newest first
        chunk_rows.sort(key=lambda r: r["created_at"], reverse=True)
    except Exception:
        # If any database models/queries fail (e.g., during initial setup), provide an empty list
        logger.warning("Database query failed in chunking_home. Returning empty chunk list.")
        chunk_rows = []

    ctx.update({
        "page_title": "RAG - Chunking",
        "chunk_rows": chunk_rows,
    })

    return render(request, "chunking.html", ctx)