# financial_statements.py  — drop-in with optional Gemini analysis
from __future__ import annotations
from typing import Tuple, Iterable

import os, re, html, logging
from decimal import Decimal, InvalidOperation

from django.apps import apps
from django.conf import settings
from django.db.models import Q, CharField
from django.db.models.functions import Cast
from django.db.models.expressions import Value

log = logging.getLogger(__name__)

# -------------------- ID normalisers --------------------
_DIGITS = re.compile(r"\D+")

def _digits(s: str | None) -> str:
    return "" if not s else _DIGITS.sub("", str(s))

def _norm_abn_candidates(abn: str | None) -> list[str]:
    d = _digits(abn)
    return [] if not d else list({d, d.zfill(11)})

def _norm_acn_candidates(acn: str | None) -> list[str]:
    d = _digits(acn)
    return [] if not d else list({d, d.zfill(9)})

# -------------------- DB + model helpers --------------------
def _db_aliases() -> list[str]:
    preferred = ["efs_data_db", "efs_sales_db", "efs_risk_db", "efs_finance_db", "default"]
    configured = set((settings.DATABASES or {}).keys())
    ordered = [a for a in preferred if a in configured]
    return ordered or ["default"]

def _get_financial_model():
    for label in ("efs_data_financial", "efs_data_financial.core", "core", "efs_data"):
        try:
            m = apps.get_model(label, "FinancialData")
            if m:
                return m
        except LookupError:
            pass
    for m in apps.get_models():
        if m.__name__ == "FinancialData":
            return m
    raise LookupError("FinancialData model not found — check INSTALLED_APPS and migrations.")

# -------------------- main query helper --------------------
def _query_financial_rows(*, abn: str | None, acn: str | None, tx: str | None) -> tuple[str | list[str], list]:
    """
    Try very hard to find rows:
      1) Exact abn/acn (digits-only) in CharFields.
      2) Fallback: search inside JSON blobs (raw/financials/profit_loss/balance_sheet/cash_flow).
      3) Fallback: transaction_id inside JSON if provided.
    Returns (alias_used OR list_of_aliases_tried, rows).
    """
    FinancialData = _get_financial_model()
    abn_cands = _norm_abn_candidates(abn)
    acn_cands = _norm_acn_candidates(acn)

    tried: list[str] = []

    for alias in _db_aliases():
        tried.append(alias)
        qs = FinancialData.objects.using(alias).all()

        # 1) direct CharField matches
        direct = Q()
        if abn_cands:
            direct |= Q(abn__in=abn_cands)
        if acn_cands:
            direct |= Q(acn__in=acn_cands)

        if direct:
            q1 = qs.filter(direct).order_by("-timestamp")
            if q1.exists():
                rows = list(q1[:5])
                log.info("[FIN] Found %d rows via CharField in '%s'", len(rows), alias)
                return alias, rows

        # 2) JSON fallbacks
        jf = Q()
        for c in abn_cands:
            jf |= (Q(raw__abn=c) | Q(financials__abn=c) | Q(profit_loss__abn=c) |
                   Q(balance_sheet__abn=c) | Q(cash_flow__abn=c))
        for c in acn_cands:
            jf |= (Q(raw__acn=c) | Q(financials__acn=c) | Q(profit_loss__acn=c) |
                   Q(balance_sheet__acn=c) | Q(cash_flow__acn=c))

        if jf:
            q2 = qs.filter(jf).order_by("-timestamp")
            if q2.exists():
                rows = list(q2[:5])
                log.info("[FIN] Found %d rows via JSON in '%s'", len(rows), alias)
                return alias, rows

        # 3) transaction id in JSON
        if tx:
            q3 = qs.filter(Q(raw__transaction_id=tx) | Q(raw__tx=tx) | Q(raw__transactionId=tx)).order_by("-timestamp")
            if q3.exists():
                rows = list(q3[:5])
                log.info("[FIN] Found %d rows via tx in '%s'", len(rows), alias)
                return alias, rows

        # 4) tiny extra: cast ABN/ACN to string and compare
        if abn_cands or acn_cands:
            q4 = qs.annotate(abn_str=Cast("abn", CharField()), acn_str=Cast("acn", CharField()))
            cf = Q()
            for c in abn_cands:
                cf |= Q(abn_str=c) | Q(abn_str=Value(c))
            for c in acn_cands:
                cf |= Q(acn_str=c) | Q(acn_str=Value(c))
            q4 = q4.filter(cf).order_by("-timestamp")
            if q4.exists():
                rows = list(q4[:5])
                log.info("[FIN] Found %d rows via cast match in '%s'", len(rows), alias)
                return alias, rows

    # nothing anywhere
    log.warning("[FIN] No rows found. Tried: %s", ", ".join(tried))
    return tried, []

# -------------------- table renderers --------------------
_MONEY_RX = re.compile(r"[,\s$]")
_DATE_COL_RX = re.compile(r"^\d{1,2}-[A-Za-z]{3}-\d{2,4}$")   # e.g. 30-Jun-23
_YEAR_RX = re.compile(r"^(19|20)\d{2}$")                      # e.g. 2023

def _num(x) -> Decimal:
    if x is None:
        return Decimal("0")
    s = str(x).strip()
    neg = s.startswith("(") and s.endswith(")")
    if neg:
        s = s[1:-1]
    s = _MONEY_RX.sub("", s)
    try:
        d = Decimal(s) if s else Decimal("0")
    except InvalidOperation:
        d = Decimal("0")
    return -d if neg else d

def _fmt_money(d: Decimal) -> str:
    q = (d or Decimal("0")).quantize(Decimal("0.01"))
    return f"${q:,.2f}"

def _safe(rows):
    return rows if isinstance(rows, list) else []

def _pick_year_columns(rows):
    years = set()
    for r in _safe(rows):
        for k in r.keys():
            if _YEAR_RX.match(str(k)):
                years.add(int(k))
    return [str(y) for y in sorted(years, reverse=True)[:3]]

def _pick_date_columns(rows):
    dates = set()
    for r in _safe(rows):
        for k in r.keys():
            if _DATE_COL_RX.match(str(k)):
                dates.add(str(k))
    return sorted(dates)

def _label_key_for_row(row, fallback_keys):
    if "Line Item" in row:
        return "Line Item"
    non_dates = [k for k in row.keys()
                 if not _DATE_COL_RX.match(str(k)) and not _YEAR_RX.match(str(k))]
    return non_dates[-1] if non_dates else (fallback_keys[-1] if fallback_keys else "Account")

def _render_pl_table(rows) -> str:
    rows = _safe(rows)
    years = _pick_year_columns(rows)

    head = (
        "<table border='1' cellpadding='6' cellspacing='0'>"
        "<thead><tr><th>Line Item</th>" +
        "".join(f"<th>{html.escape(y)}</th>" for y in years) +
        "</tr></thead><tbody>"
    )

    body_parts = []
    for r in rows[:400]:
        label = html.escape(str(r.get("Line Item", "")))
        tds = []
        for y in years:
            tds.append(f"<td style='text-align:right'>{_fmt_money(_num(r.get(y)))}</td>")
        body_parts.append(f"<tr><td>{label}</td>{''.join(tds)}</tr>")

    if years:
        totals = []
        for y in years:
            s = sum((_num(r.get(y)) for r in rows), Decimal("0"))
            totals.append(f"<td style='text-align:right;font-weight:600'>{_fmt_money(s)}</td>")
        body_parts.append(f"<tr><td style='font-weight:600'>Total (simple sum)</td>{''.join(totals)}</tr>")

    return head + "".join(body_parts) + "</tbody></table>"

def _render_bs_table(rows) -> str:
    rows = _safe(rows)
    dates = _pick_date_columns(rows)
    head_cols = "".join(f"<th>{html.escape(d)}</th>" for d in dates) if dates else "<th>Value</th>"
    head = (
        "<table border='1' cellpadding='6' cellspacing='0'>"
        f"<thead><tr><th>Account</th>{head_cols}</tr></thead><tbody>"
    )

    body_parts = []
    for r in rows[:400]:
        label_key = _label_key_for_row(r, list(r.keys()))
        label = html.escape(str(r.get(label_key, "")))
        if dates:
            tds = [f"<td style='text-align:right'>{_fmt_money(_num(r.get(d)))}</td>" for d in dates]
            body_parts.append(f"<tr><td>{label}</td>{''.join(tds)}</tr>")
        else:
            # Fallback: one numeric value if we can't find any date columns
            numeric_val = ""
            for k, v in r.items():
                if k == label_key:
                    continue
                d = _num(v)
                if d != 0:
                    numeric_val = _fmt_money(d)
                    break
            body_parts.append(f"<tr><td>{label}</td><td style='text-align:right'>{numeric_val}</td></tr>")

    return head + "".join(body_parts) + "</tbody></table>"

# ---------- derive year + company ----------
_WS_RX = re.compile(r"\s+")

def _smart_title(s: str) -> str:
    if not s:
        return s
    t = _WS_RX.sub(" ", s.strip())
    if t == t.lower():
        t = t.title()
    fixes = {"Pty": "Pty", "Ltd": "Ltd", "Pty Ltd": "Pty Ltd", "Abn": "ABN", "Acn": "ACN"}
    for k, v in fixes.items():
        t = re.sub(rf"\b{k}\b", v, t)
    return t

def _derive_year_from_rows(pl_rows, bs_rows) -> str | None:
    ys = _pick_year_columns(pl_rows)
    if ys:
        try:
            return str(max(int(y) for y in ys if str(y).isdigit()))
        except Exception:
            pass
    dates = _pick_date_columns(bs_rows)
    best = None
    for s in dates:
        try:
            parts = s.split("-")
            if len(parts) == 3:
                yr = parts[2].strip()
                if len(yr) == 2:
                    yr = f"20{yr}" if int(yr) <= 49 else f"19{yr}"
                best = max(best or 0, int(yr))
        except Exception:
            continue
    return str(best) if best else None

def _extract_company_name(rec) -> str | None:
    for attr in ("company_name", "name"):
        nm = getattr(rec, attr, None)
        if nm and str(nm).strip():
            return _smart_title(str(nm))
    candidates = ("company_name", "company", "companyName", "name", "entity", "business_name", "trading_name")

    def _walk(obj):
        if isinstance(obj, dict):
            for k in candidates:
                if k in obj and obj[k]:
                    return _smart_title(str(obj[k]))
            for k, v in obj.items():
                ks = str(k).lower().replace(" ", "").replace("_", "")
                if any(ks == c.lower().replace("_", "") for c in candidates) and v:
                    return _smart_title(str(v))
            for v in obj.values():
                hit = _walk(v)
                if hit: return hit
        elif isinstance(obj, list):
            for it in obj:
                hit = _walk(it)
                if hit: return hit
        return None

    for attr in ("raw", "financials", "profit_loss", "balance_sheet", "cash_flow"):
        blob = getattr(rec, attr, None)
        hit = _walk(blob)
        if hit: return hit
    return None

# ---------- OPTIONAL: Gemini analysis ----------
def _maybe_analyze_with_gemini(company: str, abn: str | None, acn: str | None,
                               year: str | None, pl_rows, bs_rows) -> str | None:
    """
    Calls Google Gemini (if GEMINI_API_KEY present) to produce a brief analytical paragraph.
    Safe no-op if the lib or key is missing.
    """
    api_key = getattr(settings, "GEMINI_API_KEY", None) or os.environ.get("GEMINI_API_KEY")
    if not api_key:
        return None

    try:
        import google.generativeai as genai
    except Exception as e:
        log.warning("Gemini library not available: %s", e)
        return None

    try:
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel("gemini-1.5-pro")

        # Build a compact but structured prompt
        prompt = (
            "You are a credit analyst. Given a company's Profit & Loss rows and Balance Sheet rows "
            "as JSON lists of objects, write a concise (<=120 words) assessment highlighting revenue trend, "
            "gross margin direction, expense pressure, leverage/liquidity cues, and any red flags. "
            "Be specific with numbers where obvious, but do not invent missing figures.\n\n"
            f"Company: {company or 'Unknown'}\nABN: {abn or '-'}  ACN: {acn or '-'}  Year: {year or '-'}\n"
            f"P&L rows JSON:\n{pl_rows}\n\nBalance Sheet rows JSON:\n{bs_rows}\n"
        )

        resp = model.generate_content(prompt)
        text = getattr(resp, "text", None) or (resp.candidates[0].content.parts[0].text if getattr(resp, "candidates", None) else "")
        return text.strip() if text else None
    except Exception as e:
        log.warning("Gemini analysis failed: %s", e)
        return None



# ---- robust row matching helpers ----
_WS_RX = re.compile(r"\s+")

def _norm_label(s: str) -> str:
    # lowercase, collapse whitespace, strip colons
    return _WS_RX.sub(" ", (s or "").strip().lower().replace(":", ""))

def _row_by_label(rows: list[dict], *candidates: str) -> dict | None:
    """Exact-ish match against 'Line Item' using tolerant normalization."""
    if not isinstance(rows, list):
        return None
    cand_norm = [_norm_label(c) for c in candidates]
    # 1) exact-ish
    for r in rows:
        lab = _norm_label(str(r.get("Line Item", "")))
        if lab in cand_norm:
            return r
    # 2) contains-ish (fallback)
    for r in rows:
        lab = _norm_label(str(r.get("Line Item", "")))
        if any(c in lab for c in cand_norm):
            return r
    return None








def run_analysis(
    abn: str | None = None,
    acn: str | None = None,
    transaction_id: str | None = None,
    *,
    facility_type: str | None = None,              # "BL", "IFIF", "TF"
    proposed_debt_service: Decimal | float | int | None = None,  # annual debt service for DSCR
    include_gemini: bool = True,
) -> Tuple[str, str]:
    """
    Financial Statements underwriting-style analysis.
    Returns (summary:str, table_html:str).

    Enhancements vs prior version:
      - Revenue trend / margin / profitability analysis
      - Earnings + cash flow commentary (best-effort)
      - DSCR (when debt service is provided or inferable)
      - Liquidity (current ratio, working capital)
      - Leverage (debt-to-equity)
      - IFIF/TF-oriented commentary (receivables / margin sufficiency)
      - Risk flags
      - Gemini is optional overlay, not source of truth
    """
    alias_or_list, rows = _query_financial_rows(abn=abn, acn=acn, tx=transaction_id)

    e = lambda s: html.escape(str(s or ""), quote=True)
    ident = abn or acn or transaction_id or ""
    ident_type = "ABN" if abn else ("ACN" if acn else "Transaction ID")
    facility = (facility_type or "").strip().upper() or "GENERAL"

    # -------------------- no rows --------------------
    if not rows:
        searched = ", ".join(alias_or_list) if isinstance(alias_or_list, list) else (alias_or_list or "")
        summary = (
            f"No financial statements found for {ident_type}={e(ident)} "
            f"(searched DB aliases: {searched}). "
            "Tip: ensure ABN/ACN matches storage (digits only)."
        )
        return summary, "<p><em>No financial data found.</em></p>"

    # -------------------- helpers (local to this function) --------------------
    def _to_dec(x):
        try:
            return _num(x)
        except Exception:
            return Decimal("0")

    def _pct(n: Decimal | None, d: Decimal | None) -> Decimal | None:
        try:
            if n is None or d is None or d == 0:
                return None
            return (n / d) * Decimal("100")
        except Exception:
            return None

    def _ratio(n: Decimal | None, d: Decimal | None) -> Decimal | None:
        try:
            if n is None or d is None or d == 0:
                return None
            return n / d
        except Exception:
            return None

    def _fmt_pct(x: Decimal | None, ndp: int = 1) -> str:
        if x is None:
            return "—"
        q = Decimal("1").scaleb(-ndp)  # 10^-ndp
        try:
            return f"{x.quantize(q)}%"
        except Exception:
            return f"{round(float(x), ndp)}%"

    def _fmt_x(x: Decimal | None, ndp: int = 2) -> str:
        if x is None:
            return "—"
        try:
            q = Decimal("1").scaleb(-ndp)
            return f"{x.quantize(q)}x"
        except Exception:
            return f"{round(float(x), ndp)}x"

    def _growth_pct(curr: Decimal | None, prev: Decimal | None) -> Decimal | None:
        try:
            if curr is None or prev is None or prev == 0:
                return None
            return ((curr - prev) / abs(prev)) * Decimal("100")
        except Exception:
            return None

    def _first_nonzero(*vals):
        for v in vals:
            if v is None:
                continue
            try:
                if Decimal(v) != 0:
                    return Decimal(v)
            except Exception:
                continue
        return None

    def _clean_year_key(row_keys):
        # Prefer YYYY first, then date columns
        years = [str(k) for k in row_keys if _YEAR_RX.match(str(k))]
        if years:
            return sorted(years, reverse=True)
        dates = [str(k) for k in row_keys if _DATE_COL_RX.match(str(k))]
        return sorted(dates, reverse=True)

    def _extract_period_keys(pl_rows, bs_rows, cf_rows):
        # Primary analysis period based on P&L years if possible
        years = _pick_year_columns(pl_rows)
        if years:
            return years, years[0], (years[1] if len(years) > 1 else None)
        # fallback to BS dates
        bdates = _pick_date_columns(bs_rows)
        if bdates:
            return bdates, bdates[-1], (bdates[-2] if len(bdates) > 1 else None)
        # fallback to CF rows
        # try infer from first row keys
        for r in (cf_rows or []):
            ks = _clean_year_key(r.keys())
            if ks:
                return ks, ks[0], (ks[1] if len(ks) > 1 else None)
        return [], None, None

    def _row_value(row: dict | None, period_key: str | None) -> Decimal | None:
        if not row or not period_key:
            return None
        try:
            return _to_dec(row.get(period_key))
        except Exception:
            return None

    def _row_any_value_for_periods(row: dict | None, *period_keys: str | None) -> Decimal | None:
        for pk in period_keys:
            v = _row_value(row, pk)
            if v is not None:
                return v
        return None

    def _row_match_any(rows_list, candidates: list[str]) -> dict | None:
        # use your robust global helper first
        hit = _row_by_label(rows_list or [], *candidates)
        if hit:
            return hit

        # fallback: scan any non-date/non-year label key (for BS / CF rows that may not use "Line Item")
        cand_norm = [_norm_label(c) for c in candidates]
        for r in rows_list or []:
            if not isinstance(r, dict):
                continue
            label_key = _label_key_for_row(r, list(r.keys()))
            lab = _norm_label(str(r.get(label_key, "")))
            if lab in cand_norm or any(c in lab for c in cand_norm):
                return r
        return None

    def _find_from_groups(rows_list, grouped_candidates: list[list[str]]) -> dict | None:
        for group in grouped_candidates:
            hit = _row_match_any(rows_list, group)
            if hit:
                return hit
        return None

    def _infer_total_debt(bs_rows, latest_key, prev_key=None):
        # Try direct total borrowings first, else sum current + non-current debt style rows
        total_borrowings = _find_from_groups(bs_rows, [
            ["total borrowings"],
            ["borrowings"],
            ["interest bearing liabilities"],
            ["interest-bearing liabilities"],
            ["bank loans"],
            ["loans payable"],
            ["debt"],
            ["total debt"],
        ])
        if total_borrowings:
            return _row_value(total_borrowings, latest_key), _row_value(total_borrowings, prev_key)

        curr_debt = _find_from_groups(bs_rows, [
            ["current borrowings"],
            ["current debt"],
            ["short term borrowings"],
            ["short-term borrowings"],
            ["bank overdraft"],
            ["overdraft"],
            ["current loans"],
            ["current interest bearing liabilities"],
        ])
        noncurr_debt = _find_from_groups(bs_rows, [
            ["non-current borrowings"],
            ["non current borrowings"],
            ["non-current debt"],
            ["long term borrowings"],
            ["long-term borrowings"],
            ["long term debt"],
            ["non-current loans"],
            ["non-current interest bearing liabilities"],
        ])
        curr_latest = _row_value(curr_debt, latest_key) or Decimal("0")
        noncurr_latest = _row_value(noncurr_debt, latest_key) or Decimal("0")
        curr_prev = _row_value(curr_debt, prev_key) or Decimal("0")
        noncurr_prev = _row_value(noncurr_debt, prev_key) or Decimal("0")

        if (curr_latest != 0) or (noncurr_latest != 0):
            return (curr_latest + noncurr_latest), (curr_prev + noncurr_prev)
        return None, None

    def _build_metric_table(metrics: dict, risk_flags: list[str]) -> str:
        rows_html = []

        def add_row(label, value):
            if value is None or value == "":
                return
            rows_html.append(
                f"<tr><td>{html.escape(label)}</td><td style='text-align:right'>{html.escape(str(value))}</td></tr>"
            )

        add_row("Facility Type", metrics.get("facility_type"))
        add_row("Analysis Year (latest)", metrics.get("latest_period"))
        add_row("Revenue (latest)", metrics.get("revenue_latest_fmt"))
        add_row("Revenue (previous)", metrics.get("revenue_prev_fmt"))
        add_row("Revenue Growth", metrics.get("revenue_growth_fmt"))
        add_row("Gross Profit (latest)", metrics.get("gp_latest_fmt"))
        add_row("Gross Margin (latest)", metrics.get("gp_margin_latest_fmt"))
        add_row("Gross Margin (previous)", metrics.get("gp_margin_prev_fmt"))
        add_row("Net Profit (latest)", metrics.get("np_latest_fmt"))
        add_row("Net Margin (latest)", metrics.get("net_margin_latest_fmt"))
        add_row("EBITDA (latest)", metrics.get("ebitda_latest_fmt"))
        add_row("Operating Cash Flow (latest)", metrics.get("ocf_latest_fmt"))
        add_row("Debt Service (annual)", metrics.get("debt_service_fmt"))
        add_row("DSCR", metrics.get("dscr_fmt"))
        add_row("Current Assets", metrics.get("ca_latest_fmt"))
        add_row("Current Liabilities", metrics.get("cl_latest_fmt"))
        add_row("Current Ratio", metrics.get("current_ratio_fmt"))
        add_row("Working Capital", metrics.get("working_capital_fmt"))
        add_row("Total Debt", metrics.get("debt_latest_fmt"))
        add_row("Total Equity", metrics.get("equity_latest_fmt"))
        add_row("Debt-to-Equity", metrics.get("debt_to_equity_fmt"))
        add_row("Trade Receivables", metrics.get("receivables_latest_fmt"))
        add_row("DSO (est.)", metrics.get("dso_fmt"))
        add_row("Receivables Turnover (est.)", metrics.get("receivables_turnover_fmt"))

        flags_html = ""
        if risk_flags:
            lis = "".join(f"<li>{html.escape(f)}</li>" for f in risk_flags)
            flags_html = (
                "<div style='margin-top:10px'>"
                "<strong>Risk flags / watchouts</strong>"
                f"<ul style='margin:6px 0 0 18px'>{lis}</ul>"
                "</div>"
            )

        return (
            "<h3 style='margin-top:16px'>Credit Metrics &amp; Underwriting Analysis</h3>"
            "<table border='1' cellpadding='6' cellspacing='0'>"
            "<thead><tr><th>Metric</th><th>Value</th></tr></thead>"
            f"<tbody>{''.join(rows_html)}</tbody></table>"
            f"{flags_html}"
        )

    # -------------------- most recent record --------------------
    rec = rows[0]
    company = (_extract_company_name(rec) or "").strip()
    year = getattr(rec, "year", None)

    # Extract JSON blobs
    pl = rec.profit_loss or rec.financials or []
    bs = rec.balance_sheet or []
    cf = getattr(rec, "cash_flow", None) or []
    if not isinstance(pl, list):
        pl = []
    if not isinstance(bs, list):
        bs = []
    if not isinstance(cf, list):
        cf = []

    # Render base tables
    pl_html = "<h3>Profit &amp; Loss</h3>" + _render_pl_table(pl)
    bs_html = "<h3 style='margin-top:16px'>Balance Sheet</h3>" + _render_bs_table(bs)

    # Optional cash flow table render (simple re-use of BS renderer style if present)
    cf_html = ""
    if cf:
        # cash flow often has "Line Item" + years, so use PL renderer if year columns exist else BS renderer
        if _pick_year_columns(cf):
            cf_html = "<h3 style='margin-top:16px'>Cash Flow</h3>" + _render_pl_table(cf)
        else:
            cf_html = "<h3 style='margin-top:16px'>Cash Flow</h3>" + _render_bs_table(cf)

    # -------------------- deterministic underwriting metrics --------------------
    periods, p_latest, p_prev = _extract_period_keys(pl, bs, cf)

    # --- P&L rows (broad alias coverage) ---
    revenue_row = _find_from_groups(pl, [
        ["total income"],
        ["total revenue"],
        ["revenue"],
        ["sales"],
        ["turnover"],
        ["total trading revenue"],
        ["trading revenue"],
    ]) or {}

    gross_profit_row = _find_from_groups(pl, [
        ["gross profit"],
        ["trading profit"],
    ]) or {}

    gross_margin_pct_row = _find_from_groups(pl, [
        ["gross profit (%)"],
        ["gross profit %"],
        ["gross margin %"],
        ["gross margin (%)"],
    ]) or {}

    expenses_row = _find_from_groups(pl, [
        ["total expenses"],
        ["operating expenses"],
        ["expenses"],
    ]) or {}

    net_profit_row = _find_from_groups(pl, [
        ["net profit"],
        ["net profit/(loss)"],
        ["profit/(loss) before distribution"],
        ["profit after tax"],
        ["net profit after tax"],
        ["profit/(loss)"],
    ]) or {}

    ebitda_row = _find_from_groups(pl, [
        ["ebitda"],
        ["earnings before interest tax depreciation and amortisation"],
        ["earnings before interest, tax, depreciation and amortisation"],
    ]) or {}

    ebit_row = _find_from_groups(pl, [
        ["ebit"],
        ["operating profit"],
        ["earnings before interest and tax"],
    ]) or {}

    depn_row = _find_from_groups(pl, [
        ["depreciation"],
        ["depreciation expense"],
    ]) or {}

    amort_row = _find_from_groups(pl, [
        ["amortisation"],
        ["amortization"],
        ["amortisation expense"],
        ["amortization expense"],
    ]) or {}

    interest_exp_row = _find_from_groups(pl, [
        ["interest expense"],
        ["finance costs"],
        ["interest paid"],
        ["borrowing costs"],
    ]) or {}

    tax_exp_row = _find_from_groups(pl, [
        ["income tax expense"],
        ["tax expense"],
        ["income tax"],
    ]) or {}

    # --- Balance sheet rows ---
    current_assets_row = _find_from_groups(bs, [
        ["total current assets"],
        ["current assets"],
    ]) or {}

    current_liabilities_row = _find_from_groups(bs, [
        ["total current liabilities"],
        ["current liabilities"],
    ]) or {}

    total_assets_row = _find_from_groups(bs, [
        ["total assets"],
    ]) or {}

    total_liabilities_row = _find_from_groups(bs, [
        ["total liabilities"],
    ]) or {}

    equity_row = _find_from_groups(bs, [
        ["total equity"],
        ["equity"],
        ["net assets"],
        ["shareholders equity"],
        ["shareholder funds"],
    ]) or {}

    cash_row = _find_from_groups(bs, [
        ["cash"],
        ["cash at bank"],
        ["cash and cash equivalents"],
    ]) or {}

    receivables_row = _find_from_groups(bs, [
        ["trade debtors"],
        ["accounts receivable"],
        ["trade receivables"],
        ["receivables"],
        ["debtors"],
    ]) or {}

    inventory_row = _find_from_groups(bs, [
        ["inventory"],
        ["inventories"],
        ["stock"],
    ]) or {}

    debt_latest, debt_prev = _infer_total_debt(bs, p_latest, p_prev)

    # --- Cash flow rows ---
    ocf_row = _find_from_groups(cf, [
        ["net cash provided by operating activities"],
        ["net cash from operating activities"],
        ["net cash flow from operating activities"],
        ["cash flows from operating activities"],
        ["operating cash flow"],
        ["net cash from operations"],
    ]) or {}

    capex_row = _find_from_groups(cf, [
        ["purchase of property plant and equipment"],
        ["purchase of property, plant and equipment"],
        ["capital expenditure"],
        ["capex"],
    ]) or {}

    debt_repay_row = _find_from_groups(cf, [
        ["repayment of borrowings"],
        ["repayment of loans"],
        ["loan repayments"],
        ["principal repayments"],
    ]) or {}

    interest_paid_cf_row = _find_from_groups(cf, [
        ["interest paid"],
        ["finance costs paid"],
    ]) or {}

    # -------------------- pull values --------------------
    rev_latest = _row_value(revenue_row, p_latest)
    rev_prev = _row_value(revenue_row, p_prev)

    gp_latest = _row_value(gross_profit_row, p_latest)
    gp_prev = _row_value(gross_profit_row, p_prev)

    exp_latest = _row_value(expenses_row, p_latest)
    np_latest = _row_value(net_profit_row, p_latest)
    np_prev = _row_value(net_profit_row, p_prev)

    # EBITDA (prefer explicit row, else derive)
    ebitda_latest = _row_value(ebitda_row, p_latest)
    ebitda_prev = _row_value(ebitda_row, p_prev)
    if (ebitda_latest is None or ebitda_latest == 0):
        ebit_latest = _row_value(ebit_row, p_latest)
        depn_latest = _row_value(depn_row, p_latest)
        amort_latest = _row_value(amort_row, p_latest)
        if ebit_latest is not None:
            ebitda_latest = (ebit_latest or Decimal("0")) + (depn_latest or Decimal("0")) + (amort_latest or Decimal("0"))
        elif np_latest is not None:
            # weak fallback: NP + interest + tax + depn + amort
            int_latest = _row_value(interest_exp_row, p_latest) or Decimal("0")
            tax_latest = _row_value(tax_exp_row, p_latest) or Decimal("0")
            depn_latest = _row_value(depn_row, p_latest) or Decimal("0")
            amort_latest = _row_value(amort_row, p_latest) or Decimal("0")
            ebitda_latest = (np_latest or Decimal("0")) + int_latest + tax_latest + depn_latest + amort_latest

    if (ebitda_prev is None or ebitda_prev == 0):
        ebit_prev = _row_value(ebit_row, p_prev)
        depn_prev = _row_value(depn_row, p_prev)
        amort_prev = _row_value(amort_row, p_prev)
        if ebit_prev is not None:
            ebitda_prev = (ebit_prev or Decimal("0")) + (depn_prev or Decimal("0")) + (amort_prev or Decimal("0"))

    # Gross margin %
    gp_margin_latest = _pct(gp_latest, rev_latest)
    gp_margin_prev = _pct(gp_prev, rev_prev)

    # If a gross margin % row exists and computed margin is unavailable, use stated % row
    stated_gp_margin_latest = _row_value(gross_margin_pct_row, p_latest)
    stated_gp_margin_prev = _row_value(gross_margin_pct_row, p_prev)
    if gp_margin_latest is None and stated_gp_margin_latest is not None:
        gp_margin_latest = stated_gp_margin_latest
    if gp_margin_prev is None and stated_gp_margin_prev is not None:
        gp_margin_prev = stated_gp_margin_prev

    net_margin_latest = _pct(np_latest, rev_latest)

    # OCF / CF
    ocf_latest = _row_value(ocf_row, p_latest)
    ocf_prev = _row_value(ocf_row, p_prev)
    capex_latest = _row_value(capex_row, p_latest)
    debt_repay_latest = _row_value(debt_repay_row, p_latest)
    interest_paid_cf_latest = _row_value(interest_paid_cf_row, p_latest)

    # Balance sheet values
    ca_latest = _row_value(current_assets_row, p_latest)
    cl_latest = _row_value(current_liabilities_row, p_latest)
    total_assets_latest = _row_value(total_assets_row, p_latest)
    total_liab_latest = _row_value(total_liabilities_row, p_latest)
    equity_latest = _row_value(equity_row, p_latest)
    cash_latest = _row_value(cash_row, p_latest)
    receivables_latest = _row_value(receivables_row, p_latest)
    inventory_latest = _row_value(inventory_row, p_latest)

    # derive equity if missing
    if (equity_latest is None or equity_latest == 0) and total_assets_latest is not None and total_liab_latest is not None:
        equity_latest = (total_assets_latest or Decimal("0")) - (total_liab_latest or Decimal("0"))

    # leverage & liquidity
    current_ratio = _ratio(ca_latest, cl_latest)
    working_capital = None
    if ca_latest is not None and cl_latest is not None:
        working_capital = ca_latest - cl_latest

    debt_to_equity = None
    if debt_latest is not None and equity_latest is not None and equity_latest != 0:
        debt_to_equity = debt_latest / equity_latest

    # Receivables metrics (best effort)
    receivables_turnover = None
    dso = None
    if rev_latest is not None and rev_latest != 0 and receivables_latest is not None:
        try:
            receivables_turnover = rev_latest / receivables_latest if receivables_latest != 0 else None
            dso = (receivables_latest / rev_latest) * Decimal("365")
        except Exception:
            pass

    # DSCR (prefer OCF; fallback EBITDA)
    debt_service = None
    if proposed_debt_service is not None:
        try:
            debt_service = Decimal(str(proposed_debt_service))
        except Exception:
            debt_service = None
    else:
        # weak inference from CF statement if available
        inferred_principal = abs(debt_repay_latest) if debt_repay_latest is not None else None
        inferred_interest = None
        if interest_paid_cf_latest is not None:
            inferred_interest = abs(interest_paid_cf_latest)
        else:
            pl_interest = _row_value(interest_exp_row, p_latest)
            inferred_interest = abs(pl_interest) if pl_interest is not None else None

        if inferred_principal is not None or inferred_interest is not None:
            debt_service = (inferred_principal or Decimal("0")) + (inferred_interest or Decimal("0"))
            if debt_service == 0:
                debt_service = None

    cashflow_available = _first_nonzero(ocf_latest, ebitda_latest, np_latest)
    dscr = _ratio(cashflow_available, debt_service) if debt_service is not None else None

    # Revenue growth / profitability trends
    revenue_growth = _growth_pct(rev_latest, rev_prev)
    gp_growth = _growth_pct(gp_latest, gp_prev)
    np_growth = _growth_pct(np_latest, np_prev)

    # -------------------- policy/risk flags --------------------
    risk_flags: list[str] = []
    info_flags: list[str] = []

    if rev_latest is None or rev_latest == 0:
        risk_flags.append("Revenue could not be reliably extracted from P&L rows.")
    if gp_latest is None:
        risk_flags.append("Gross Profit could not be reliably extracted; margin analysis may be incomplete.")
    if np_latest is None:
        risk_flags.append("Net Profit could not be reliably extracted from P&L rows.")
    if not cf:
        info_flags.append("Cash flow statement not present; OCF/DSCR may rely on EBITDA or partial data.")
    elif ocf_latest is None:
        info_flags.append("Cash flow statement found, but Operating Cash Flow line could not be reliably identified.")

    if revenue_growth is not None and revenue_growth < Decimal("0"):
        risk_flags.append(f"Revenue declined YoY ({_fmt_pct(revenue_growth)}); confirm driver (one-off loss, sector slowdown, churn, seasonality).")

    if gp_margin_latest is not None and gp_margin_latest < Decimal("10"):
        risk_flags.append(f"Gross margin is thin at {_fmt_pct(gp_margin_latest)}; financing costs may pressure viability (especially IFIF/TF).")
    elif gp_margin_latest is not None and gp_margin_latest < Decimal("15") and facility in {"IFIF", "TF"}:
        risk_flags.append(f"Gross margin {_fmt_pct(gp_margin_latest)} may be tight for {facility} after fees/delays/discounts.")

    if net_margin_latest is not None and net_margin_latest < Decimal("0"):
        risk_flags.append(f"Net margin is negative ({_fmt_pct(net_margin_latest)}); loss-making profile increases serviceability risk.")

    if current_ratio is not None and current_ratio < Decimal("1.0"):
        risk_flags.append(f"Current ratio {_fmt_x(current_ratio)} indicates tight liquidity (<1.0x).")
    elif current_ratio is not None and current_ratio < Decimal("1.2"):
        info_flags.append(f"Current ratio {_fmt_x(current_ratio)} is acceptable but tight; monitor working capital and payment timing.")

    if working_capital is not None and working_capital < 0:
        risk_flags.append(f"Working capital deficit of {_fmt_money(working_capital)}.")

    if equity_latest is not None and equity_latest < 0:
        risk_flags.append(f"Negative equity ({_fmt_money(equity_latest)}); requires strong mitigants.")
    if debt_to_equity is not None and equity_latest is not None and equity_latest > 0:
        if debt_to_equity > Decimal("3.0"):
            risk_flags.append(f"High leverage: debt-to-equity {_fmt_x(debt_to_equity)}.")
        elif debt_to_equity > Decimal("2.0"):
            info_flags.append(f"Moderately elevated leverage: debt-to-equity {_fmt_x(debt_to_equity)}.")

    # DSCR policy (BL)
    if facility == "BL":
        if dscr is None:
            risk_flags.append("DSCR could not be calculated (missing debt service and/or cash flow inputs).")
        elif dscr < Decimal("1.2"):
            risk_flags.append(f"DSCR {_fmt_x(dscr)} is below policy target (>1.2x) for term loans.")
        else:
            info_flags.append(f"DSCR {_fmt_x(dscr)} is above policy target (>1.2x) for term loans.")

    # IFIF / TF specific flags
    if facility == "IFIF":
        if dso is not None and dso > Decimal("75"):
            risk_flags.append(f"Estimated DSO {_fmt_x(dso, 1).replace('x',' days')} is elevated; review aging / recourse / debtor quality.")
        if receivables_turnover is None:
            info_flags.append("Receivables turnover / DSO could not be estimated (missing receivables or revenue rows).")
        if gp_margin_latest is not None and gp_margin_latest < Decimal("20"):
            info_flags.append("IFIF margin buffer looks tight; confirm fee load, dilution risk, and recourse capacity.")
        else:
            info_flags.append("For IFIF, validate debtor concentration, aging, disputes/dilution, and payment behaviour before setting limits.")

    if facility == "TF":
        if gp_margin_latest is not None and gp_margin_latest < Decimal("15"):
            risk_flags.append("TF gross margin buffer appears thin; confirm markup covers fees and trading volatility.")
        else:
            info_flags.append("For TF, confirm client markup on goods covers facility fees and preserves profit after delays/FX/logistics risk.")
        if current_ratio is not None and current_ratio < Decimal("1.0"):
            risk_flags.append("TF structure may be strained by weak liquidity; align tenor to verified trade cycle.")

    # General watchouts
    if receivables_turnover is not None and dso is not None:
        if dso > Decimal("90"):
            risk_flags.append("Receivables collection appears slow (high DSO), increasing cash conversion risk.")
    if ocf_latest is not None and np_latest is not None and np_latest > 0 and ocf_latest < 0:
        risk_flags.append("Positive earnings but negative operating cash flow; review earnings quality and working capital movements.")

    # -------------------- structured narrative sections --------------------
    sections: list[str] = []

    # Revenue & trends
    revenue_lines: list[str] = []
    if p_prev and rev_prev is not None and p_latest and rev_latest is not None:
        growth_txt = f" ({_fmt_pct(revenue_growth)})" if revenue_growth is not None else ""
        revenue_lines.append(
            f"Revenue trend: {p_prev} {_fmt_money(rev_prev)} → {p_latest} {_fmt_money(rev_latest)}{growth_txt}."
        )
    elif p_latest and rev_latest is not None:
        revenue_lines.append(f"Revenue ({p_latest}): {_fmt_money(rev_latest)}.")
    revenue_lines.append(
        "Review sales trend over at least 2 years and year-to-date (if available); note seasonality and calibrate limits to peak vs slow periods."
    )
    sections.append("Revenue Trends\n- " + "\n- ".join(revenue_lines))

    # Earnings & cash flow
    ecf_lines: list[str] = []
    if p_latest and ebitda_latest is not None:
        ecf_lines.append(f"EBITDA ({p_latest}): {_fmt_money(ebitda_latest)}.")
    if p_latest and np_latest is not None:
        nm_txt = f" (net margin {_fmt_pct(net_margin_latest)})" if net_margin_latest is not None else ""
        ecf_lines.append(f"Net profit ({p_latest}): {_fmt_money(np_latest)}{nm_txt}.")
    if p_latest and ocf_latest is not None:
        ecf_lines.append(f"Operating cash flow ({p_latest}): {_fmt_money(ocf_latest)}.")
    else:
        ecf_lines.append("Operating cash flow not reliably extracted; use caution and consider manual review of cash flow statement.")
    if debt_service is not None:
        ecf_lines.append(f"Debt service (annual, provided/inferred): {_fmt_money(debt_service)}.")
    if dscr is not None:
        dscr_rule = " (target >1.2x for BL)" if facility == "BL" else ""
        ecf_lines.append(f"DSCR (cash flow available / debt service): {_fmt_x(dscr)}{dscr_rule}.")
    elif facility == "BL":
        ecf_lines.append("DSCR could not be calculated for BL due to missing debt service and/or cash flow inputs.")
    sections.append("Earnings and Cash Flow\n- " + "\n- ".join(ecf_lines))

    # Margin / profitability
    margin_lines: list[str] = []
    if gp_latest is not None and p_latest:
        gm_txt = f" (gross margin {_fmt_pct(gp_margin_latest)})" if gp_margin_latest is not None else ""
        margin_lines.append(f"Gross profit ({p_latest}): {_fmt_money(gp_latest)}{gm_txt}.")
    if p_prev and gp_prev is not None and gp_growth is not None:
        margin_lines.append(f"Gross profit YoY change: {_fmt_pct(gp_growth)}.")
    if exp_latest is not None and p_latest:
        margin_lines.append(f"Expenses ({p_latest}): {_fmt_money(exp_latest)}.")
    if facility in {"IFIF", "TF"}:
        if facility == "IFIF":
            margin_lines.append(
                "For IFIF, confirm gross margin is sufficient so the client can absorb fees, slower payments, or invoice discounts while maintaining operations and recourse repayment capacity."
            )
        if facility == "TF":
            margin_lines.append(
                "For TF, confirm trading markup/gross margin covers fees and still leaves acceptable profit after normal execution risk."
            )
    else:
        margin_lines.append(
            "Thin margins increase sensitivity to financing costs and revenue volatility; validate margin sustainability if growth is being relied upon."
        )
    sections.append("Gross Margins and Profitability\n- " + "\n- ".join(margin_lines))

    # Balance sheet / leverage / liquidity
    bsl_lines: list[str] = []
    if current_ratio is not None:
        bsl_lines.append(f"Current ratio: {_fmt_x(current_ratio)}.")
    if working_capital is not None:
        bsl_lines.append(f"Working capital: {_fmt_money(working_capital)}.")
    if debt_latest is not None:
        bsl_lines.append(f"Total debt (best effort): {_fmt_money(debt_latest)}.")
    if equity_latest is not None:
        bsl_lines.append(f"Total equity (best effort): {_fmt_money(equity_latest)}.")
    if debt_to_equity is not None:
        bsl_lines.append(f"Debt-to-equity: {_fmt_x(debt_to_equity)}.")
    else:
        bsl_lines.append("Debt-to-equity could not be calculated reliably (missing debt and/or equity rows).")
    bsl_lines.append(
        "Review for undisclosed liabilities, director loans, contingent liabilities, and any material balance-sheet changes not obvious from extracted rows."
    )
    sections.append("Balance Sheet and Leverage\n- " + "\n- ".join(bsl_lines))

    # Facility-specific section
    facility_lines: list[str] = []
    if facility == "BL":
        facility_lines.append("Focus on serviceability, DSCR (>1.2x target), liquidity buffer, and repayment resilience under downside scenarios.")
    elif facility == "IFIF":
        if receivables_turnover is not None:
            facility_lines.append(f"Receivables turnover (est.): {_fmt_x(receivables_turnover)}.")
        if dso is not None:
            facility_lines.append(f"DSO (est.): {dso.quantize(Decimal('0.1'))} days.")
        facility_lines.append("For IFIF, review debtor aging, top debtor concentration, dilution/disputes, and concentration limits before approval.")
    elif facility == "TF":
        facility_lines.append("For TF, ensure tenor aligns to trade cycle and exit source; validate margin sufficiency for fees, delays, and execution risk.")
        if inventory_latest is not None:
            facility_lines.append(f"Inventory (latest, if extracted): {_fmt_money(inventory_latest)}.")
    else:
        facility_lines.append("Specify facility_type='BL', 'IFIF', or 'TF' for tailored commentary and policy thresholds.")
    sections.append("Facility-Specific Considerations\n- " + "\n- ".join(facility_lines))

    # Risk flags section
    if risk_flags or info_flags:
        rf_lines = [f"RISK: {x}" for x in risk_flags] + [f"INFO: {x}" for x in info_flags]
        sections.append("Key Risks and Watchouts\n- " + "\n- ".join(rf_lines))

    deterministic_summary = "\n\n".join(sections).strip()

    # -------------------- optional Gemini overlay (supplementary only) --------------------
    gemini_text = None
    if include_gemini:
        # include cash flow rows in prompt only indirectly by current helper signature; keep existing helper unchanged
        gemini_text = _maybe_analyze_with_gemini(
            company=company, abn=abn, acn=acn, year=(year or _derive_year_from_rows(pl, bs)),
            pl_rows=pl, bs_rows=bs,
        )

    ai_block = ""
    if gemini_text:
        ai_block = (
            "<div class='analysis-output' style='margin:8px 0;padding:8px;border:1px dashed #ccc;background:#fafafa'>"
            "<strong>AI analysis (Gemini, supplementary):</strong> "
            f"{html.escape(gemini_text)}"
            "</div>"
        )

    # -------------------- summary header --------------------
    timestamp = getattr(rec, "timestamp", None)
    stamp = timestamp.isoformat(sep=" ", timespec="seconds") if timestamp else "n/a"
    alias_str = alias_or_list if isinstance(alias_or_list, str) else "multi"

    derived_year = year or _derive_year_from_rows(pl, bs)
    header_bits = [f"{ident_type}={e(ident)}", f"facility={facility}", f"db='{alias_str}'"]
    if derived_year:
        header_bits.insert(1, f"year={e(derived_year)}")

    header = f"[{stamp}] Financial statements found"
    if company:
        header += f" for {html.escape(company)}"
    header += " — " + "; ".join(header_bits)

    # -------------------- compact one-line executive summary (sales notes friendly) --------------------
    exec_parts = []
    if p_latest and rev_latest is not None:
        exec_parts.append(f"Revenue {p_latest} {_fmt_money(rev_latest)}")
    if revenue_growth is not None:
        exec_parts.append(f"YoY {_fmt_pct(revenue_growth)}")
    if gp_margin_latest is not None:
        exec_parts.append(f"GP% {_fmt_pct(gp_margin_latest)}")
    if net_margin_latest is not None:
        exec_parts.append(f"Net margin {_fmt_pct(net_margin_latest)}")
    if dscr is not None:
        exec_parts.append(f"DSCR {_fmt_x(dscr)}")
    if current_ratio is not None:
        exec_parts.append(f"Current ratio {_fmt_x(current_ratio)}")
    if debt_to_equity is not None:
        exec_parts.append(f"D/E {_fmt_x(debt_to_equity)}")
    if risk_flags:
        exec_parts.append(f"{len(risk_flags)} risk flag(s)")

    executive_line = " | ".join(exec_parts) if exec_parts else "Underwriting summary generated from available financial statement rows."

    summary = f"{executive_line}\n\n{deterministic_summary}\n\n{header}"

    # -------------------- HTML output assembly --------------------
    metrics_payload = {
        "facility_type": facility,
        "latest_period": p_latest or "—",
        "revenue_latest_fmt": _fmt_money(rev_latest) if rev_latest is not None else "—",
        "revenue_prev_fmt": _fmt_money(rev_prev) if rev_prev is not None else "—",
        "revenue_growth_fmt": _fmt_pct(revenue_growth) if revenue_growth is not None else "—",
        "gp_latest_fmt": _fmt_money(gp_latest) if gp_latest is not None else "—",
        "gp_margin_latest_fmt": _fmt_pct(gp_margin_latest) if gp_margin_latest is not None else "—",
        "gp_margin_prev_fmt": _fmt_pct(gp_margin_prev) if gp_margin_prev is not None else "—",
        "np_latest_fmt": _fmt_money(np_latest) if np_latest is not None else "—",
        "net_margin_latest_fmt": _fmt_pct(net_margin_latest) if net_margin_latest is not None else "—",
        "ebitda_latest_fmt": _fmt_money(ebitda_latest) if ebitda_latest is not None else "—",
        "ocf_latest_fmt": _fmt_money(ocf_latest) if ocf_latest is not None else "—",
        "debt_service_fmt": _fmt_money(debt_service) if debt_service is not None else "—",
        "dscr_fmt": _fmt_x(dscr) if dscr is not None else "—",
        "ca_latest_fmt": _fmt_money(ca_latest) if ca_latest is not None else "—",
        "cl_latest_fmt": _fmt_money(cl_latest) if cl_latest is not None else "—",
        "current_ratio_fmt": _fmt_x(current_ratio) if current_ratio is not None else "—",
        "working_capital_fmt": _fmt_money(working_capital) if working_capital is not None else "—",
        "debt_latest_fmt": _fmt_money(debt_latest) if debt_latest is not None else "—",
        "equity_latest_fmt": _fmt_money(equity_latest) if equity_latest is not None else "—",
        "debt_to_equity_fmt": _fmt_x(debt_to_equity) if debt_to_equity is not None else "—",
        "receivables_latest_fmt": _fmt_money(receivables_latest) if receivables_latest is not None else "—",
        "dso_fmt": (f"{dso.quantize(Decimal('0.1'))} days" if dso is not None else "—"),
        "receivables_turnover_fmt": _fmt_x(receivables_turnover) if receivables_turnover is not None else "—",
    }

    metrics_html = _build_metric_table(metrics_payload, risk_flags + info_flags)

    text_summary_html = (
        "<h3 style='margin-top:16px'>Deterministic Underwriting Summary</h3>"
        "<div style='white-space:pre-wrap; border:1px solid #ddd; padding:10px; background:#fff'>"
        f"{html.escape(deterministic_summary)}"
        "</div>"
    )

    final_html = (
        ai_block
        + metrics_html
        + text_summary_html
        + pl_html
        + bs_html
        + cf_html
    )

    return summary, final_html