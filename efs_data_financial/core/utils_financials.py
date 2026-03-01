# efs_data_financial/core/utils_financials.py
from collections import defaultdict
import re
from typing import Dict, List, Tuple, Any

# "REVENUE", "DIRECT COSTS", etc.
UPPER_RE = re.compile(r'^[^a-z]*$')

# e.g. "Dec-23 ($000)" OR plain numeric "2023", "2024"
YEAR_TOKEN_RE = re.compile(r'(?:[A-Za-z]{3}-\d{2})|(?:20\d{2})')

def _coerce_number(s):
    if s is None:
        return None
    if isinstance(s, (int, float)):
        return float(s)
    txt = str(s).strip()
    if not txt:
        return None
    neg = False
    if txt.startswith('(') and txt.endswith(')'):
        neg = True
        txt = txt[1:-1]
    txt = txt.replace(',', '').replace('$', '')
    try:
        val = float(txt)
        return -val if neg else val
    except ValueError:
        return None

def _normalize_flat_dict(d: Dict[str, Any]) -> List[Dict[str, Any]]:
    rows = []
    for k, v in (d or {}).items():
        rows.append({"name": str(k).strip(), "value": v})
    return rows

def _normalize_taud_rows(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    TAUD style:
      { "": "(37,880)", "TAUD": "Production" }
    """
    out = []
    for r in rows or []:
        label = (r.get('TAUD') or r.get('label') or '').strip()
        val = r.get('')
        if val in (None, ''):
            for cand in ('value', 'amount', 'Amount', 'Value'):
                if cand in r:
                    val = r[cand]
                    break
        row = {"name": label, "value": val}
        out.append(row)
    return out

def _normalize_statement(raw: Any) -> List[Dict[str, Any]]:
    """
    Return a list of rows:
      - section headers: {"name": "...", "section": True}
      - lines:           {"name": "...", "value": number or text}
    Works for dicts OR lists of TAUD rows (legacy path).
    """
    # TAUD list
    if isinstance(raw, list) and raw and isinstance(raw[0], dict) and ('TAUD' in raw[0] or '' in raw[0]):
        rows = _normalize_taud_rows(raw)
    elif isinstance(raw, dict):
        rows = _normalize_flat_dict(raw)
    else:
        rows = []

    cleaned = []
    for r in rows:
        name = (r.get('name') or '').strip()
        val = r.get('value')
        if name.lower() in ('year number', 'status', 'financial year'):
            continue
        if (not val and name and UPPER_RE.match(name)):
            cleaned.append({"name": name, "section": True})
            continue
        num = _coerce_number(val)
        cleaned.append({
            "name": name or "—",
            "value": num if num is not None else (val if val not in (None, '') else None)
        })
    return cleaned







# utils_financials.py
import re

MONTHS = ["jan","feb","mar","apr","may","jun","jul","aug","sep","oct","nov","dec"]

LABEL_KEY_HINTS = (
    "financial year",
    "balance sheet items",
    "balance sheet",
    "profit & loss",
    "profit and loss",
    "p&l",
    "item", "items",
    "label", "name",
)

def _detect_matrix_schema(raw):
    """
    Detect matrix-style rows and return:
      (label_key, [(col_name, period_id, label_str), ...])

    - If a column looks like a real year (e.g. 2023, Dec-24 ($000)), we use:
        period_id = year (int), label_str = "2023"
    - If a column looks like a month (e.g. Jul-01, August 02), we use:
        period_id = running index to preserve order, label_str = "JULY"/"AUGUST"/...
    """
    if not (isinstance(raw, list) and raw and isinstance(raw[0], dict)):
        return None, []

    # 1) pick label column
    label_key = None
    for k in raw[0].keys():
        norm = k.replace('\ufeff', '').strip().lower()
        if any(h in norm for h in LABEL_KEY_HINTS):
            label_key = k
            break
    if not label_key:
        # first non-yearish column
        def _is_yearish(col: str) -> bool:
            return bool(re.search(r'(20\d{2})|([A-Za-z]{3}-\d{2})', str(col)))
        for k in raw[0].keys():
            if not _is_yearish(k):
                label_key = k
                break
    if not label_key:
        return None, []

    # 2) collect period columns
    year_cols = []
    running_idx = 0  # preserves visible order for month-mode
    for k in raw[0].keys():
        if k == label_key:
            continue
        token = str(k)
        # real year?
        m4 = re.search(r'(20\d{2})', token)
        if m4:
            y = int(m4.group(1))
            year_cols.append((k, y, str(y)))  # (col_name, period_id, label="2024")
            continue

        # month-style? e.g. "Jul-01", "August 02", "SEP", "September"
        t = token.replace('\ufeff', '').strip()
        low = t.lower()
        mon = None
        for i, m in enumerate(MONTHS, start=1):
            if re.match(rf'^{m}\b', low):  # starts with month name
                mon = i
                break
        if mon:
            # label is the month name (uppercased nicely)
            label = MONTHS[mon-1].upper()
            # use running index as period id to keep UI order as-is
            year_cols.append((k, 10_000 + running_idx, label))
            running_idx += 1
            continue

        # not a period column
    if not year_cols:
        return None, []

    return label_key, year_cols




from collections import defaultdict

def pivot_multi_year(year_and_raws):
    sections = defaultdict(lambda: defaultdict(dict))

    period_labels = []     # visible labels in order (e.g., ["JULY","AUGUST","SEPTEMBER"] or ["2024","2023"])
    period_ids_in_order = []  # internal ids matching labels
    seen_period_ids = set()

    for yr_hint, raw in year_and_raws:
        label_key, year_cols = _detect_matrix_schema(raw)
        if label_key and year_cols:
            # keep provided order (we already encoded order in period_id for month-mode)
            current_section = "__ungrouped__"

            # remember label order once
            for col_name, pid, lab in year_cols:
                if pid not in seen_period_ids:
                    seen_period_ids.add(pid)
                    period_ids_in_order.append(pid)
                    period_labels.append(lab)

            for row in raw:
                label = (row.get(label_key) or "").replace('\ufeff', '').strip()
                # detect section headers (all-caps + all values empty)
                all_empty = True
                values_for_periods = {}
                for col_name, pid, _lab in year_cols:
                    v = row.get(col_name)
                    num = _coerce_number(v)
                    if num is not None:
                        values_for_periods[pid] = num
                        all_empty = False

                if label and all_empty and UPPER_RE.match(label):
                    current_section = label
                    continue
                if not label:
                    continue

                for pid, val in values_for_periods.items():
                    sections[current_section][label][pid] = val
            continue

        # legacy single-year path unchanged
        rows = _normalize_statement(raw)
        current_section = "__ungrouped__"
        if rows:
            pid = yr_hint
            if pid not in seen_period_ids:
                seen_period_ids.add(pid)
                period_ids_in_order.append(pid)
                period_labels.append(str(pid))
        for r in rows:
            if r.get('section'):
                current_section = r['name']
                continue
            nm = r.get('name') or "—"
            val = r.get('value')
            sections[current_section][nm][pid] = val

    # Build output in the recorded order
    years = period_labels  # these are what your UI renders as column headers

    prio = ["REVENUE","DIRECT COSTS","COST OF SALES","OVERHEADS","EXPENSES","EBITDA","__ungrouped__"]
    ordered_keys = sorted(sections.keys(), key=lambda k: (prio.index(k) if k in prio else len(prio), k))

    out_sections = []
    for sec in ordered_keys:
        lines = []
        for line_name, by_pid in sections[sec].items():
            # map values following the period order
            values = {}
            for pid, lab in zip(period_ids_in_order, years):
                if pid in by_pid:
                    # when we return to FE we still key by the visible label
                    values[lab] = by_pid[pid]
            lines.append({"name": line_name, "values": values})
        lines.sort(key=lambda L: (0 if 'total' not in L['name'].lower() else 1, L['name']))
        out_sections.append({"title": sec, "lines": lines})

    return {"years": years, "sections": out_sections}

# utils_text.py
import re
from typing import Optional

def clean_ocr_text(s: Optional[str]) -> str:
    """
    Make OCR'ed text human-readable:
    - join single newlines inside paragraphs
    - keep blank lines as paragraph breaks
    - remove soft hyphens and join hyphenated line breaks
    """
    if not s:
        return ""

    t = s.replace("\r", "\n")               # normalise line endings
    t = t.replace("\u00ad", "")             # remove soft hyphen chars

    # Join words split across lines with hyphen: e.g. "work-\nflow" -> "workflow"
    t = re.sub(r"-\s*\n\s*", "", t)

    # Collapse 3+ blank lines to 2 (max paragraph break)
    t = re.sub(r"\n\s*\n\s*\n+", "\n\n", t)

    # Join single linebreaks within paragraphs -> space.
    # Do it iteratively to consume chains created by previous replacements.
    prev = None
    while prev != t:
        prev = t
        t = re.sub(r"([^\s])\n(?!\n)([^\s])", r"\1 \2", t)

    # Tidy spaces
    t = re.sub(r"[ \t]{2,}", " ", t)
    t = re.sub(r"[ \t]+\n", "\n", t)

    return t.strip()




#_______-----------__________

# debtors credit report analysis


#_______-----------__________


# efs_data_financial/utils.py

def summarize_debtor_credit_report(instance):
    """
    Builds a short, readable summary from a DebtorsCreditReport instance.

    Semantic guarantees:
    - abn / acn        → CLIENT identifiers
    - debtor_abn/acn   → DEBTOR identifiers
    """

    report = instance.report or {}
    summary = report.get("summary", {}) or {}

    # --------------------
    # CLIENT identifiers
    # --------------------
    client_abn = (
        summary.get("clientAbn")
        or instance.abn
        or "—"
    )

    client_acn = (
        summary.get("clientAcn")
        or instance.acn
        or "—"
    )

    # --------------------
    # DEBTOR identifiers
    # --------------------
    debtor_abn = (
        summary.get("debtorAbn")
        or instance.debtor_abn
        or "—"
    )

    debtor_acn = (
        summary.get("debtorAcn")
        or instance.debtor_acn
        or "—"
    )

    debtor_name = instance.debtor_name or "Unnamed debtor"

    # --------------------
    # Credit summary
    # --------------------
    score_block = summary.get("score", {}) or {}
    score_value = score_block.get("value")
    score_out_of = score_block.get("outOf")
    score_band = score_block.get("band")

    if score_value is not None and score_out_of:
        score_str = f"{score_value}/{score_out_of}"
    elif score_value is not None:
        score_str = str(score_value)
    else:
        score_str = "N/A"

    enquiries = summary.get("creditEnquiries")
    if enquiries is None:
        enquiries = instance.credit_enquiries or 0

    # --------------------
    # ANZSIC
    # --------------------
    anz = report.get("anzsic", {}) or {}
    anz_code = anz.get("anzsicCode") or anz.get("groupCode") or "—"
    anz_desc = anz.get("anzsicDescription") or anz.get("groupDescription") or "—"
    division = anz.get("divisionDescription") or "—"
    subdivision = anz.get("subdivisionDescription") or "—"

    # --------------------
    # Event counts
    # --------------------
    def _count(key):
        v = report.get(key, [])
        return len(v) if isinstance(v, list) else 0

    counts = {
        "Insolvencies": _count("insolvencies"),
        "Court Judgements": _count("courtJudgements"),
        "Payment Defaults": _count("paymentDefaults"),
        "Mercantile Enquiries": _count("mercantileEnquiries"),
        "Loans": _count("loans"),
    }

    # --------------------
    # Compose summary
    # --------------------
    parts = [
        f"Client ABN: {client_abn}",
        f"Client ACN: {client_acn}",
        f"Debtor: {debtor_name}",
        f"Debtor ABN: {debtor_abn}",
        f"Debtor ACN: {debtor_acn}",
        f"Credit enquiries: {enquiries}",
        f"Score: {score_str}" + (f" (Band: {score_band})" if score_band else ""),
        f"ANZSIC: {anz_code} – {anz_desc}",
        f"Division: {division}",
        f"Subdivision: {subdivision}",
        "Flags: " + ", ".join(f"{k}={v}" for k, v in counts.items()),
    ]

    if instance.state:
        parts.append(f"State: {instance.state}")
    if instance.debtor_start_date:
        parts.append(f"Relationship start: {instance.debtor_start_date}")

    return " | ".join(parts)
