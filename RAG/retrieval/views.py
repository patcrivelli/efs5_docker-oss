import logging
import requests
from django.conf import settings
from django.shortcuts import render, redirect

logger = logging.getLogger(__name__)

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

def base_context(request):
    originators = fetch_originators()
    selected_originator = None
    selected_id = request.GET.get("originators")
    if selected_id:
        for o in originators:
            if str(o.get("id")) == str(selected_id):
                selected_originator = o
                break
    return {"originators": originators, "selected_originator": selected_originator}

def retrieval_home(request):
    ctx = base_context(request)
    ctx.update({"page_title": "RAG - Retrieval"})
    return render(request, "retrieval.html", ctx)

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

    return redirect("retrieval_home")






#------------------------------------


# experimental code starts here



#------------------------------------

import logging
import json
import time
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from sentence_transformers import SentenceTransformer
from pgvector.django import L2Distance

from embeddings.models import Embedding

logger = logging.getLogger(__name__)

SECTION_KEYWORDS = {
    "balance_sheet": ["balance sheet", "assets", "liabilities", "equity", "current ratio"],
    "income_statement": ["income statement", "profit and loss", "revenue", "gross margin", "operating income", "net income", "eps"],
    "cash_flow": ["cash flow", "operating activities", "investing activities", "financing activities", "free cash flow"],
    "notes": ["notes to the financial statements", "accounting policies", "fair value", "impairment", "leases"],
}

@csrf_exempt
def test_retrieval(request):
    if request.method != "POST":
        return JsonResponse({"message": "POST required"}, status=405)

    try:
        body = json.loads(request.body.decode("utf-8"))
        query_text = (body.get("query") or "").strip()
        top_k = int(body.get("top_k") or 5)
        section_hint = (body.get("section_hint") or "").lower()  # optional
    except Exception as e:
        logger.error("Invalid JSON: %s", e)
        return JsonResponse({"message": "Invalid JSON"}, status=400)

    if not query_text:
        return JsonResponse({"message": "Query cannot be empty"}, status=400)

    # 1) Encode query
    t0 = time.time()
    query_vec = embedding_model.encode([query_text], normalize_embeddings=True)[0]
    logger.info("Encoded query in %.2fs", time.time() - t0)

    # 2) (optional) filter by model_name if you store multiple models
    base_qs = Embedding.objects.select_related("element")\
        .filter(model_name=MODEL_NAME)

    # 3) Pull a wider candidate pool then re-rank
    CANDIDATES = max(50, top_k * 30)

    # Optional coarse pre-filter on section title text if you want (kept off by default)
    if section_hint in ("balance_sheet", "income_statement", "cash_flow", "notes"):
        # filter where section title contains the hint tokens (stored in Element.meta.section_title)
        # This uses PostgreSQL JSON lookups via Django
        base_qs = base_qs.filter(element__meta__section_title__icontains=section_hint.replace("_", " "))

    # Initial ANN order by cosine
    candidates = list(
        base_qs.order_by(CosineDistance("vector", query_vec))[:CANDIDATES]
    )

    # 4) Python re-rank using section weight + keyword boost
    kw_bonus = 1.0
    hint_keywords = SECTION_KEYWORDS.get(section_hint, [])
    query_lower = query_text.lower()

    def score(emb_obj):
        # cosine distance -> similarity
        # pgvector only gives us ordering, not the actual distance value here,
        # so compute a heuristic re-score using metadata only.
        meta = emb_obj.element.meta or {}
        sw = float(meta.get("section_weight") or 1.0)

        # keyword bonus if the chunk text or section title contains hint words
        bonus = 0.0
        if hint_keywords:
            text = (emb_obj.element.text or "").lower()
            title = (meta.get("section_title") or "").lower()
            hit = any(k in text or k in title for k in hint_keywords)
            if hit:
                bonus += 0.10  # +10%
        # small bonus if the hint is in the query itself to stabilize
        if any(k in query_lower for k in hint_keywords):
            bonus += 0.05

        # final multiplier
        return sw * (1.0 + bonus)

    # sort by our multiplier while preserving initial order (stable sort with key)
    # we use negative to sort descending on multiplier
    candidates.sort(key=lambda e: score(e), reverse=True)

    # 5) Trim to top_k and return
    out = []
    for emb in candidates[:top_k]:
        meta = emb.element.meta or {}
        out.append({
            "element_id": str(emb.element.id),
            "section_title": meta.get("section_title"),
            "section_weight": meta.get("section_weight"),
            "chunk_text": (emb.element.text or "")[:1200],  # more generous trim
        })

    return JsonResponse({"query": query_text, "section_hint": section_hint, "results": out})





# views_retrieval.py
import logging, json, time, math
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from sentence_transformers import SentenceTransformer
from pgvector.django import CosineDistance  # <-- cosine
from embeddings.models import Embedding

logger = logging.getLogger(__name__)

MODEL_NAME = "sentence-transformers/all-mpnet-base-v2"
embedding_model = SentenceTransformer(MODEL_NAME)





import logging
import json
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.utils import timezone
from .models import RetrievalLog

logger = logging.getLogger(__name__)

@csrf_exempt
def save_retrieval(request):
    """
    Save a retrieval query + results for evaluation.
    """
    if request.method != "POST":
        return JsonResponse({"message": "POST required"}, status=405)

    try:
        body = json.loads(request.body.decode("utf-8"))
        query_text = body.get("query", "").strip()
        results = body.get("results", [])
    except Exception as e:
        logger.error(f"❌ Invalid JSON in save_retrieval: {e}")
        return JsonResponse({"message": "Invalid JSON"}, status=400)

    if not query_text or not results:
        return JsonResponse({"message": "Query and results required"}, status=400)

    try:
        log = RetrievalLog.objects.create(
            query_text=query_text,
            results=results,
            created_at=timezone.now()
        )
        logger.info(f"✅ Saved retrieval log {log.id}")
        return JsonResponse({"message": "Saved successfully", "log_id": str(log.id)})
    except Exception as e:
        logger.error(f"❌ Save error: {e}", exc_info=True)
        return JsonResponse({"message": "Failed to save retrieval", "error": str(e)}, status=500)
