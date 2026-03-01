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
def ingestion_home(request):
    ctx = base_context(request)
    selected_originator = ctx.get("selected_originator")

    originator_name = (
        selected_originator.get("originator") if selected_originator else None
    )

    ctx.update({
        "page_title": "RAG - Ingestion",
        "originator_name": originator_name,
    })
    return render(request, "ingestion.html", ctx)

# ---- form handler (optional, like drawdowns) ----
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

    return redirect("ingestion_home")




# ------------------------------------

# experimental code starts here

# ------------------------------------

# apps/ingestion/views.py
import hashlib
import json
import re
from io import BytesIO
from typing import List, Dict, Any, Iterable, Tuple, Optional

from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.http import JsonResponse, HttpResponseBadRequest
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import csrf_exempt

from ingestion.models import Document, DocumentFile
from chunking.models import ExtractionRun, Element

# Optional page count (pip install pypdf)
try:
    from pypdf import PdfReader
except Exception:  # module not installed or import error
    PdfReader = None

import fitz  # PyMuPDF for PDF parsing


# ---------- Utilities ----------

def _sha256(django_file) -> str:
    """Calculate SHA-256 without loading entire file into memory at once."""
    h = hashlib.sha256()
    for chunk in django_file.chunks():
        h.update(chunk)
    # reset read pointer so Django can save it
    django_file.seek(0)
    return h.hexdigest()


def _pdf_page_count(django_file) -> Optional[int]:
    if not PdfReader:
        return None
    pos = django_file.tell()
    django_file.seek(0)
    data = django_file.read()
    django_file.seek(pos)
    try:
        reader = PdfReader(BytesIO(data))
        return len(reader.pages)
    except Exception:
        return None


def _safe_json_loads(s: Optional[str], default: Any) -> Any:
    if not s:
        return default
    try:
        return json.loads(s)
    except Exception:
        return default


# ---------- Chunking helpers (config-driven) ----------

DEFAULT_CONFIG: Dict[str, Any] = {
    "preset": "financials",
    "split_strategy": "hybrid",            # fixed | sentence | paragraph | section | hybrid
    "chunk_size_chars": 1800,
    "overlap_chars": 270,                  # ~15% of 1800
    "min_chunk_chars": 200,
    "cleanup": {
        "strip_page_numbers": True,
        "strip_headers": True,
        "strip_footers": True,
        "boilerplate_patterns": [],
    },
    "sections": {
        "patterns": [
            r"^\s*(Consolidated\s+)?(Statement|Balance\s*Sheet)\b",
            r"^\s*(Statement\s+of\s+Profit\s+and\s+Loss|Profit\s*&\s*Loss|Income\s+Statement)\b",
            r"^\s*Statement\s+of\s+Cash\s+Flows?\b",
            r"^\s*Statement\s+of\s+Changes\s+in\s+Equity\b",
            r"^\s*Notes?\s+to\s+the\s+Financial\s+Statements?\b",
            r"^\s*Auditor’s?\s+Report\b",
            r"^\s*Directors’?\s+Report\b",
        ],
        "weights": {
            "balance_sheet": 1.3,
            "profit_and_loss": 1.3,
            "cash_flow": 1.15,
            "notes": 1.1,
        },
    },
    "tables": {
        "mode": "preserve_cells",          # as_text | preserve_cells | ignore
        "min_row_chars": 10,
    },
    "ocr": {
        "enable": False,
        "keep_layout_blocks": False,
    },
    "sentence_windows": {"window": 5, "overlap": 1},
    "semantic_boundaries": {"enable": False, "threshold": 0.25},
}

_HEADER_FOOTER_MAX_LINES = 2  # how many lines at top/bottom to consider repetitive


def _compile_section_regexes(patterns: List[str]) -> List[re.Pattern]:
    out = []
    for p in patterns:
        try:
            out.append(re.compile(p, re.IGNORECASE | re.MULTILINE))
        except re.error:
            # ignore bad regex from UI
            continue
    return out


def _strip_boilerplate_lines(lines: List[str], boilerplate_regexes: List[re.Pattern]) -> List[str]:
    if not boilerplate_regexes:
        return lines
    keep = []
    for ln in lines:
        if any(rx.search(ln) for rx in boilerplate_regexes):
            continue
        keep.append(ln)
    return keep


def _strip_repeating_headers_footers(pages_text: List[str], strip_headers: bool, strip_footers: bool) -> List[str]:
    """Naive heuristic: detect lines that repeat on many pages at top/bottom."""
    if not (strip_headers or strip_footers) or not pages_text:
        return pages_text

    top_counts = {}
    bot_counts = {}

    # collect candidates
    for t in pages_text:
        lines = t.splitlines()
        if strip_headers:
            for ln in lines[:_HEADER_FOOTER_MAX_LINES]:
                ln = ln.strip()
                if ln:
                    top_counts[ln] = top_counts.get(ln, 0) + 1
        if strip_footers:
            for ln in lines[-_HEADER_FOOTER_MAX_LINES:]:
                ln = ln.strip()
                if ln:
                    bot_counts[ln] = bot_counts.get(ln, 0) + 1

    # consider "repeating" if appears on >= 1/3 of pages
    threshold = max(2, len(pages_text) // 3)
    top_repeating = {ln for ln, c in top_counts.items() if c >= threshold}
    bot_repeating = {ln for ln, c in bot_counts.items() if c >= threshold}

    cleaned = []
    for t in pages_text:
        lines = t.splitlines()
        new_lines = []
        for i, ln in enumerate(lines):
            s = ln.strip()
            if strip_headers and i < _HEADER_FOOTER_MAX_LINES and s in top_repeating:
                continue
            if strip_footers and i >= len(lines) - _HEADER_FOOTER_MAX_LINES and s in bot_repeating:
                continue
            new_lines.append(ln)
        cleaned.append("\n".join(new_lines))
    return cleaned


def _remove_page_numbers(lines: List[str]) -> List[str]:
    # simple patterns like "Page 12", "12", "12 / 200"
    rx = re.compile(r"^(page\s*)?\d+(\s*/\s*\d+)?\s*$", re.IGNORECASE)
    return [ln for ln in lines if not rx.match(ln.strip())]


def _split_into_sections(text: str, section_regexes: List[re.Pattern]) -> List[Tuple[str, str]]:
    """
    Returns list of (section_title, section_text).
    If no regex matches, returns single section 'Body'.
    """
    lines = text.splitlines()
    sections: List[Tuple[str, str]] = []
    cur_title = "Body"
    cur_buf: List[str] = []

    def flush():
        nonlocal cur_title, cur_buf, sections
        sections.append((cur_title, ("\n".join(cur_buf)).strip()))
        cur_buf = []

    for ln in lines:
        if any(rx.search(ln) for rx in section_regexes):
            # start a new section
            if cur_buf:  # flush previous
                flush()
            cur_title = ln.strip()[:200] or "Section"
            cur_buf = []
        cur_buf.append(ln)
    # flush tail
    flush()
    # remove empties
    sections = [(t, s) for (t, s) in sections if s.strip()]
    return sections or [("Body", text.strip())]


def _sentence_chunks(body: str, max_len: int, min_len: int, sent_overlap: int, win: int) -> List[str]:
    # naive sentence split; you can swap for nltk/spacy if available
    sentences = re.split(r"(?<=[\.\!\?])\s+|\n+", body.strip())
    sentences = [s for s in sentences if s.strip()]
    if not sentences:
        return []

    out: List[str] = []
    i = 0
    while i < len(sentences):
        # take window of sentences, then extend until max_len
        j = min(i + win, len(sentences))
        buf = " ".join(sentences[i:j])
        while j < len(sentences) and len(buf) + 1 + len(sentences[j]) <= max_len:
            buf = buf + " " + sentences[j]
            j += 1
        if len(buf.strip()) >= min_len:
            out.append(buf.strip())
        # overlap by `sent_overlap` sentences
        i = max(j - sent_overlap, i + 1)
    return out


def _paragraph_chunks(body: str, max_len: int, min_len: int, overlap_chars: int) -> List[str]:
    paras = re.split(r"\n{2,}", body.strip())
    paras = [p.strip() for p in paras if p.strip()]
    out: List[str] = []
    buf = ""
    for p in paras:
        if not buf:
            buf = p
            continue
        if len(buf) + 2 + len(p) <= max_len:
            buf = buf + "\n\n" + p
        else:
            if len(buf) >= min_len:
                out.append(buf)
            buf = p
    if buf and len(buf) >= min_len:
        out.append(buf)
    # apply simple char overlap between paragraph-packed chunks
    if overlap_chars > 0 and len(out) > 1:
        overlapped = []
        for k, ch in enumerate(out):
            if k < len(out) - 1:
                tail = ch[-overlap_chars:]
                nxt = out[k + 1]
                merged = (ch + "\n" + nxt[: max_len - len(tail)])[0:max_len]
                overlapped.append(merged)
            else:
                overlapped.append(ch)
        return overlapped
    return out


def _fixed_chunks(body: str, max_len: int, min_len: int, overlap_chars: int) -> List[str]:
    out: List[str] = []
    step = max(1, max_len - overlap_chars)
    for start in range(0, len(body), step):
        piece = body[start : start + max_len].strip()
        if len(piece) >= min_len:
            out.append(piece)
    return out


def _choose_section_weight(title: str, weights: Dict[str, float]) -> float:
    t = title.lower()
    if "balance" in t and "sheet" in t:
        return float(weights.get("balance_sheet", 1.0))
    if ("profit" in t and "loss" in t) or "income statement" in t:
        return float(weights.get("profit_and_loss", 1.0))
    if "cash" in t and "flow" in t:
        return float(weights.get("cash_flow", 1.0))
    if "note" in t and "financial" in t:
        return float(weights.get("notes", 1.0))
    return 1.0


def _extract_page_texts_with_tables(doc_path: str, table_mode: str) -> List[str]:
    """
    Returns list of page-level text blobs.
    NOTE: Table 'preserve_cells' is a placeholder using PyMuPDF blocks;
    swap in pdfplumber/camelot if you need structured cells.
    """
    doc = fitz.open(doc_path)
    pages = []
    for pg in doc:
        if table_mode == "ignore":
            pages.append(pg.get_text("text"))
            continue
        if table_mode == "as_text":
            pages.append(pg.get_text("text"))
            continue
        # "preserve_cells" (very light approximation): merge text by blocks/lines
        blocks = pg.get_text("blocks")  # (x0, y0, x1, y1, text, block_no, block_type, ...)
        blocks = sorted(blocks, key=lambda b: (round(b[1], 1), round(b[0], 1)))  # top->down, left->right
        lines = []
        for _, _, _, _, txt, *_ in blocks:
            if txt and txt.strip():
                # replace tabs to keep columns somewhat visible
                lines.extend([ln.replace("\t", "  ").strip() for ln in txt.splitlines()])
        pages.append("\n".join(lines))
    return pages


# ---------- Core chunker ----------

def chunk_pdf(
    document_file: DocumentFile,
    parser: str = "pymupdf",
    parser_version: str = "1.1",
    cfg: Optional[Dict[str, Any]] = None,
) -> ExtractionRun:
    """
    1. Creates an ExtractionRun record with params = cfg.
    2. Extracts and cleans text (headers/footers/boilerplate).
    3. Detects sections using regex patterns.
    4. Splits into chunks per strategy with overlap.
    5. Saves chunks into Element with rich metadata.
    """
    cfg = {**DEFAULT_CONFIG, **(cfg or {})}

    extraction_run = ExtractionRun.objects.create(
        document_file=document_file,
        parser=parser,
        parser_version=parser_version,
        params=cfg,  # store full config for lineage
    )

    # 1) Extract page texts
    table_mode = (cfg.get("tables") or {}).get("mode", "as_text")
    pages_text = _extract_page_texts_with_tables(document_file.file.path, table_mode)

    # 2) Cleanup
    cl = cfg.get("cleanup", {})
    if cl.get("strip_headers") or cl.get("strip_footers"):
        pages_text = _strip_repeating_headers_footers(
            pages_text, strip_headers=bool(cl.get("strip_headers")), strip_footers=bool(cl.get("strip_footers"))
        )

    boilerplate = [re.compile(pat, re.IGNORECASE) for pat in (cl.get("boilerplate_patterns") or [])]

    cleaned_pages: List[str] = []
    for t in pages_text:
        lines = t.splitlines()
        if cl.get("strip_page_numbers"):
            lines = _remove_page_numbers(lines)
        lines = _strip_boilerplate_lines(lines, boilerplate)
        cleaned_pages.append("\n".join(lines))

    full_text = "\n\n".join(cleaned_pages)

    # 3) Sections
    section_regexes = _compile_section_regexes((cfg.get("sections") or {}).get("patterns", []))
    sections = _split_into_sections(full_text, section_regexes)

    # 4) Split strategy / overlap
    strategy = cfg.get("split_strategy", "hybrid")
    max_len = int(cfg.get("chunk_size_chars", 1800))
    overlap_chars = int(cfg.get("overlap_chars", 0))
    min_len = int(cfg.get("min_chunk_chars", 0))
    sent_win = int((cfg.get("sentence_windows") or {}).get("window", 5))
    sent_ov = int((cfg.get("sentence_windows") or {}).get("overlap", 1))

    weights = (cfg.get("sections") or {}).get("weights", {})

    # 5) Emit Elements
    chunk_counter = 0
    for sec_title, sec_body in sections:
        if not sec_body.strip():
            continue

        # choose splitter
        chunks: List[str] = []
        if strategy == "fixed":
            chunks = _fixed_chunks(sec_body, max_len, min_len, overlap_chars)
        elif strategy == "sentence":
            chunks = _sentence_chunks(sec_body, max_len, min_len, sent_ov, sent_win)
        elif strategy == "paragraph":
            chunks = _paragraph_chunks(sec_body, max_len, min_len, overlap_chars)
        elif strategy == "section":
            # one pass fixed inside the section (ensures large sections still split)
            chunks = _fixed_chunks(sec_body, max_len, min_len, overlap_chars)
        else:  # hybrid: paragraph then fallback to fixed for overflows
            prelim = _paragraph_chunks(sec_body, max_len, min_len, overlap_chars=0)
            chunks = []
            for pc in prelim:
                if len(pc) > int(max_len * 1.25):  # oversize paragraph group
                    chunks.extend(_fixed_chunks(pc, max_len, min_len, overlap_chars))
                else:
                    chunks.append(pc)

        if not chunks:
            continue

        sec_weight = _choose_section_weight(sec_title, weights)

        # we no longer have reliable per-page numbers after concatenation; keep page_number=None
        for idx, chunk_text in enumerate(chunks):
            Element.objects.create(
                extraction=extraction_run,
                document=document_file.document,
                element_type="text",
                page_number=None,  # could be mapped using page offsets if you need per-page pointers
                start_offset=None,
                end_offset=None,
                text=chunk_text,
                meta={
                    "parser": parser,
                    "strategy": strategy,
                    "section_title": sec_title,
                    "section_weight": sec_weight,
                    "chunk_index": idx,
                    "tables_mode": table_mode,
                },
            )
            chunk_counter += 1

    # Optionally, you could update ExtractionRun.params with a stats block
    extraction_run.params["stats"] = {"chunks_created": chunk_counter}
    extraction_run.save(update_fields=["params"])

    return extraction_run


@require_POST
@csrf_exempt  # ⚠️ only for testing; remove later in production
@transaction.atomic
def upload_document(request):
    """
    Expects multipart form-data with:
      company_name, ticker_symbol (opt), fiscal_year (opt), source (default 'upload'),
      file (PDF), chunk_config_json (optional)
    """
    file = request.FILES.get("file")
    company_name = (request.POST.get("company_name") or "").strip()
    ticker_symbol = (request.POST.get("ticker_symbol") or "").strip() or None
    fiscal_year = request.POST.get("fiscal_year") or None
    source = request.POST.get("source") or "upload"

    # NEW: read widget config (hidden field)
    config_json = request.POST.get("chunk_config_json")
    chunk_cfg = _safe_json_loads(config_json, DEFAULT_CONFIG)

    if not company_name or not file:
        return HttpResponseBadRequest("company_name and file are required.")

    if fiscal_year:
        try:
            fiscal_year = int(fiscal_year)
        except ValueError:
            return HttpResponseBadRequest("fiscal_year must be an integer.")

    # Create Document (store the config for lineage)
    doc = Document.objects.create(
        company_name=company_name,
        ticker_symbol=ticker_symbol,
        fiscal_year=fiscal_year,
        source=source,
        extra={"chunking": chunk_cfg},
    )

    # Metadata for the file
    sha = _sha256(file)
    page_count = _pdf_page_count(file) if file.content_type == "application/pdf" else None
    latest = (
        DocumentFile.objects.filter(document=doc)
        .order_by("-version")
        .values_list("version", flat=True)
        .first()
    )
    next_version = (latest or 0) + 1

    doc_file = DocumentFile.objects.create(
        document=doc,
        file=file,
        original_filename=file.name,
        mime_type=getattr(file, "content_type", "application/octet-stream"),
        byte_size=file.size,
        sha256=sha,
        version=next_version,
        page_count=page_count,
        uploaded_by=None,  # no auth here
    )

    # Run chunking right after file is saved (apply widget config)
    extraction_run = None
    if file.content_type == "application/pdf":
        extraction_run = chunk_pdf(
            document_file=doc_file,
            parser="pymupdf",
            parser_version="1.1",
            cfg=chunk_cfg,
        )

    return JsonResponse(
        {
            "document_id": str(doc.id),
            "document_file_id": str(doc_file.id),
            "version": doc_file.version,
            "page_count": doc_file.page_count,
            "storage_path": doc_file.file.url,
            "extraction_run_id": str(extraction_run.id) if extraction_run else None,
        },
        status=201,
    )
