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
def embeddings_home(request):
    ctx = base_context(request)
    ctx.update({"page_title": "RAG - Embeddings"})
    return render(request, "embeddings.html", ctx)

# ---- optional originator create ----
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

    return redirect("embeddings_home")



# ------------------------------------
# experimental code starts here
# ------------------------------------

# apps/embeddings/views.py

import json
import logging
import re
from typing import Dict, Any, List, Tuple

import torch
from django.http import JsonResponse, HttpResponseBadRequest
from django.views.decorators.csrf import csrf_exempt
from django.db import transaction

from sentence_transformers import SentenceTransformer

from chunking.models import Element
from .models import Embedding

logger = logging.getLogger(__name__)

# ---- Model registry & cache ----
# If you change dimensions in the DB, update this map.
MODEL_REGISTRY: Dict[str, int] = {
    "sentence-transformers/all-mpnet-base-v2": 768,
    "sentence-transformers/all-MiniLM-L6-v2": 384,
    "intfloat/e5-large-v2": 1024,
    # "openai/text-embedding-3-large": 3072,  # (not used here; server-side API needed)
}

_model_cache: Dict[Tuple[str, str], SentenceTransformer] = {}  # key = (model_name, device)


def _get_embed_config(request) -> Dict[str, Any]:
    try:
        body = request.body.decode("utf-8") if request.body else "{}"
        data = json.loads(body or "{}")
        cfg = data.get("embedding_config") or {}
        return cfg
    except Exception:
        return {}


def _load_model(model_name: str, device: str) -> SentenceTransformer:
    # resolve device
    dev = device
    if dev == "auto":
        dev = "cuda" if torch.cuda.is_available() else "cpu"

    key = (model_name, dev)
    if key in _model_cache:
        return _model_cache[key]

    logger.info("Loading embedding model '%s' on %s", model_name, dev)
    model = SentenceTransformer(model_name, device=dev)
    _model_cache[key] = model
    return model


def _preprocess_texts(texts: List[str], lowercase: bool, ws_norm: bool) -> List[str]:
    out = []
    for t in texts:
        if t is None:
            continue
        s = t if isinstance(t, str) else str(t)
        if lowercase:
            s = s.lower()
        if ws_norm:
            s = re.sub(r"[ \t]+", " ", s)
            s = re.sub(r"\s+\n", "\n", s)
        out.append(s.strip())
    return out


def _is_numeric_only(s: str) -> bool:
    # "numeric only" ~ digits, punctuation, currency symbols, whitespace
    return bool(s) and not re.search(r"[A-Za-z]", s)


def _filter_texts_for_embedding(
    elements: List[Element],
    min_chars: int,
    max_chars: int,
    drop_numeric_only: bool,
    deduplicate: bool,
    lowercase: bool,
    ws_norm: bool,
) -> Tuple[List[str], List[str]]:
    """
    Returns (texts, element_ids_as_str) after preprocessing & filtering.
    """
    seen = set()
    texts: List[str] = []
    ids: List[str] = []

    raw_texts = []
    raw_ids = []
    for el in elements:
        if not el.text or not el.text.strip():
            continue
        raw_texts.append(el.text)
        raw_ids.append(str(el.id))

    proc_texts = _preprocess_texts(raw_texts, lowercase=lowercase, ws_norm=ws_norm)

    for text, el_id in zip(proc_texts, raw_ids):
        n = len(text)
        if min_chars and n < min_chars:
            continue
        if max_chars and n > max_chars:
            continue
        if drop_numeric_only and _is_numeric_only(text):
            continue
        if deduplicate:
            h = hash(text)
            if h in seen:
                continue
            seen.add(h)
        texts.append(text)
        ids.append(el_id)

    return texts, ids


def _normalize_if_needed(vectors, normalize: bool):
    if not normalize:
        return vectors
    # L2 normalize row-wise
    import numpy as np

    norms = np.linalg.norm(vectors, axis=1, keepdims=True)
    norms[norms == 0.0] = 1.0
    return vectors / norms


@csrf_exempt
@transaction.atomic
def create_embeddings(request):
    """
    Create/update embeddings according to UI knobs.

    Expected JSON body:
    {
      "embedding_config": {
        "model": "...",
        "device": "auto|cuda|cpu",
        "precision": "auto|fp32|fp16|bf16",
        "batch_size": 32,
        "normalize_embeddings": true,
        "preprocess": {"lowercase": false, "normalize_whitespace": true},
        "filter": {"min_chars": 50, "max_chars": 4000, "drop_numeric_only": true, "deduplicate": true},
        "scope": "new_only|model_mismatch|all",
        "limit": 1000,
        "retrieval_defaults": {...}  # ignored here; persist elsewhere if you have a Run model
      }
    }
    """
    cfg = _get_embed_config(request)

    model_name = cfg.get("model") or "sentence-transformers/all-mpnet-base-v2"
    device = cfg.get("device") or "auto"
    precision = (cfg.get("precision") or "auto").lower()
    batch_size = int(cfg.get("batch_size") or 32)
    normalize_embeddings = bool(cfg.get("normalize_embeddings") if cfg.get("normalize_embeddings") is not None else True)

    pp = cfg.get("preprocess") or {}
    lowercase = bool(pp.get("lowercase") or False)
    ws_norm = bool(pp.get("normalize_whitespace") if pp.get("normalize_whitespace") is not None else True)

    flt = cfg.get("filter") or {}
    min_chars = int(flt.get("min_chars") or 0)
    max_chars = int(flt.get("max_chars") or 0)
    drop_numeric_only = bool(flt.get("drop_numeric_only") or False)
    deduplicate = bool(flt.get("deduplicate") or True)

    scope = (cfg.get("scope") or "new_only").lower()
    limit = int(cfg.get("limit") or 1000)

    # --- Enforce pgvector dim compatibility (your field is 768) ---
    dim = MODEL_REGISTRY.get(model_name)
    if dim is None:
        return HttpResponseBadRequest(f"Unknown/unsupported model '{model_name}'. Add it to MODEL_REGISTRY with its dimension.")
    PG_DIM = 768  # from Embedding.vector definition
    if dim != PG_DIM:
        return HttpResponseBadRequest(
            f"Model '{model_name}' outputs dim={dim} but your Embedding.vector is dim={PG_DIM}. "
            f"Choose a 768-dim model or change your pgvector field to dimensions={dim}."
        )

    # --- Select elements per scope ---
    qs = Element.objects.filter(element_type="text")
    if scope == "new_only":
        qs = qs.filter(embedding__isnull=True)
    elif scope == "model_mismatch":
        # include elements with no embedding OR embedding created with a different model_name
        qs = qs.filter().exclude(embedding__model_name=model_name)
    elif scope == "all":
        pass
    else:
        return HttpResponseBadRequest("Invalid 'scope'. Use one of: new_only, model_mismatch, all.")

    if limit:
        qs = qs[:limit]

    elements = list(qs)
    if not elements:
        return JsonResponse({"message": "No target elements found for the selected scope."})

    # --- Preprocess & filter texts ---
    texts, ids = _filter_texts_for_embedding(
        elements=elements,
        min_chars=min_chars,
        max_chars=max_chars,
        drop_numeric_only=drop_numeric_only,
        deduplicate=deduplicate,
        lowercase=lowercase,
        ws_norm=ws_norm,
    )

    if not texts:
        return JsonResponse({"message": "No valid text after filtering."})

    # --- Load model on device ---
    model = _load_model(model_name, device=device)

    # (Light) precision hint — SentenceTransformers doesn't expose full AMP here.
    # We keep it simple; if you want true FP16/BF16, instantiate the model with that dtype in your env.
    if precision in ("fp16", "bf16") and next(model.parameters()).is_cuda:
        try:
            dtype = torch.float16 if precision == "fp16" else torch.bfloat16
            model = model.to(dtype=dtype)
        except Exception:
            # Don't fail the run if dtype move isn't supported
            logger.warning("Could not switch model to %s precision; continuing with default.", precision)

    # --- Encode in batches ---
    try:
        vectors = model.encode(
            texts,
            batch_size=batch_size,
            convert_to_numpy=True,
            normalize_embeddings=normalize_embeddings,
            show_progress_bar=False,
        )
    except TypeError:
        # for older sentence-transformers versions without normalize_embeddings arg
        vectors = model.encode(
            texts,
            batch_size=batch_size,
            convert_to_numpy=True,
            show_progress_bar=False,
        )
        vectors = _normalize_if_needed(vectors, normalize_embeddings)

    # --- Upsert embeddings ---
    created, updated = 0, 0
    details = []

    for el_id, vec in zip(ids, vectors):
        try:
            element = Element.objects.get(id=el_id)
        except Element.DoesNotExist:
            continue

        # OneToOne: create or update
        emb, was_created = Embedding.objects.get_or_create(
            element=element,
            defaults={"vector": vec.tolist(), "model_name": model_name},
        )
        if was_created:
            created += 1
            details.append({"element_id": el_id, "embedding_id": str(emb.id), "action": "created"})
        else:
            # scope may ask to re-embed; update vector + model_name
            emb.vector = vec.tolist()
            emb.model_name = model_name
            emb.save(update_fields=["vector", "model_name", "created_at"])
            updated += 1
            details.append({"element_id": el_id, "embedding_id": str(emb.id), "action": "updated"})

    return JsonResponse(
        {
            "created": created,
            "updated": updated,
            "processed": len(ids),
            "model": model_name,
            "device": device,
            "normalize_embeddings": normalize_embeddings,
            "details": details[:200],  # avoid huge payloads
        },
        status=201 if created or updated else 200,
    )
