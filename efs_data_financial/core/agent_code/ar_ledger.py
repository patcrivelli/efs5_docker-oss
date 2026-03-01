# efs_data_financial/core/agent_code/ar_ledger.py
import logging
import html
from datetime import datetime
from decimal import Decimal

from django.apps import apps
from django.core.exceptions import ImproperlyConfigured

log = logging.getLogger(__name__)


# ----------------------------
# Model resolvers
# ----------------------------
def _get_uploaded_ledger_model():
    """
    Resolve UploadedLedgerData robustly regardless of app label.
    """
    for label in ("efs_data_financial", "efs_data_financial.core", "core", "efs_data"):
        try:
            model = apps.get_model(label, "UploadedLedgerData")
            if model is not None:
                return model
        except LookupError:
            pass

    for m in apps.get_models():
        if m.__name__ == "UploadedLedgerData":
            return m

    labels = sorted({m._meta.app_label for m in apps.get_models()})
    raise ImproperlyConfigured(
        "Could not resolve model UploadedLedgerData. "
        "Ensure the defining app is in INSTALLED_APPS and migrations are applied. "
        f"Known app labels: {labels}"
    )


def _get_model_by_name(model_name: str):
    """
    Resolve a model by class name across installed apps.
    Returns the model class or None.
    """
    for m in apps.get_models():
        if m.__name__ == model_name:
            return m
    return None


def _get_navar_line_model():
    """
    Resolve NAVARLine model if available in this service.
    """
    return _get_model_by_name("NAVARLine")


def _get_nav_snapshot_model():
    """
    Resolve NetAssetValueSnapshot model if available in this service.
    """
    return _get_model_by_name("NetAssetValueSnapshot")


# ----------------------------
# Helpers
# ----------------------------
def _to_number(txt):
    """
    Parse ledger currency-like strings: '$', ',', spaces, parentheses for negatives.
    """
    if txt is None or txt == "":
        return 0.0
    s = str(txt).strip()
    neg = s.startswith("(") and s.endswith(")")
    if neg:
        s = s[1:-1]
    s = s.replace("$", "").replace(",", "").strip()
    try:
        val = float(s) if s else 0.0
    except Exception:
        return 0.0
    return -val if neg else val


def _d(v) -> Decimal:
    """
    Safe Decimal conversion.
    """
    if v is None or v == "":
        return Decimal("0")
    if isinstance(v, Decimal):
        return v
    try:
        return Decimal(str(v))
    except Exception:
        return Decimal("0")


def _money(d: Decimal) -> str:
    try:
        return f"${d:,.2f}"
    except Exception:
        return "$0.00"


def _pct(d: Decimal) -> str:
    try:
        return f"{d:.2f}%"
    except Exception:
        return "0.00%"





def _is_truthy(v) -> bool:
    if isinstance(v, bool):
        return v
    if v is None:
        return False
    s = str(v).strip().lower()
    return s in {"1", "true", "t", "yes", "y", "on"}

def _line_is_nominated(ln) -> bool:
    """
    Robust nominated-row detection for NAVARLine.
    Supports bool/int/string values.
    """
    # Primary expected field
    if hasattr(ln, "nominated"):
        return _is_truthy(getattr(ln, "nominated", False))

    # Fallbacks if schema changed / alternate field names exist
    for alt in ("is_nominated", "selected", "included", "include_in_nav"):
        if hasattr(ln, alt):
            return _is_truthy(getattr(ln, alt, False))

    return False





# ----------------------------
# Main analysis
# ----------------------------
def run_analysis(abn=None, acn=None, transaction_id=None):
    """
    Returns (summary:str, table_html:str)
    Includes:
      - UploadedLedgerData raw rollup
      - Latest NAV AR snapshot rollup (if NAV models are available in this service)
    """
    ident = abn or acn or ""
    ident_type = "ABN" if abn else ("ACN" if acn else "ID")

    log.info("[AR] run_analysis start %s=%s tx=%s", ident_type, ident, transaction_id)
    print(f"[AR] run_analysis: {ident_type}={ident} tx={transaction_id}")

    e = lambda s: html.escape(str(s or ""), quote=True)
    stamp = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")

    # ============================================================
    # 1) UploadedLedgerData analysis (raw ledger)
    # ============================================================
    UploadedLedgerData = _get_uploaded_ledger_model()
    qs = UploadedLedgerData.objects.all()

    if abn:
        qs = qs.filter(abn=abn)
    elif acn:
        qs = qs.filter(acn=acn)
    if transaction_id:
        qs = qs.filter(transaction_id=transaction_id)

    total_aged_raw = 0.0
    count_rows = 0
    per_debtor_raw = {}  # debtor -> sum aged_receivables

    # NOTE: expects UploadedLedgerData has fields debtor, aged_receivables
    for row in qs.only("debtor", "aged_receivables"):
        val = _to_number(getattr(row, "aged_receivables", None))
        debtor = (getattr(row, "debtor", None) or "Unknown").strip() or "Unknown"
        per_debtor_raw[debtor] = per_debtor_raw.get(debtor, 0.0) + val
        total_aged_raw += val
        count_rows += 1

    top5_raw_lines = []
    if total_aged_raw > 0:
        ranked = sorted(per_debtor_raw.items(), key=lambda kv: kv[1], reverse=True)[:5]
        for debtor, amount in ranked:
            share = (amount / total_aged_raw) * 100.0
            top5_raw_lines.append(f"- {debtor}: {share:.2f}% (${amount:,.2f})")

    # ============================================================
    # 2) NAV snapshot analysis (latest saved AR state)
    # ============================================================
    nav_snapshot = None
    nav_lines = []
    nav_available = False
    nav_note = None

    NavSnapshot = _get_nav_snapshot_model()
    NAVARLine = _get_navar_line_model()

    if not NavSnapshot or not NAVARLine:
        nav_note = (
            "NAV snapshot not available in this service "
            "(NetAssetValueSnapshot / NAVARLine models not installed here)."
        )
    else:
        try:
            nav_qs = NavSnapshot.objects.filter(source_tab="AR")
            if abn:
                nav_qs = nav_qs.filter(abn=abn)
            elif acn and "acn" in [f.name for f in NavSnapshot._meta.fields]:
                nav_qs = nav_qs.filter(acn=acn)

            if transaction_id:
                nav_qs = nav_qs.filter(transaction_id=transaction_id)

            # newest snapshot
            nav_snapshot = nav_qs.order_by("-created_at", "-id").first()

            if nav_snapshot:
                nav_available = True

                # Load all lines first, then apply robust nominated filtering in Python.
                # This avoids bad assumptions if nominated is stored as non-bool types.
                nav_lines_all = list(
                    NAVARLine.objects.filter(snapshot=nav_snapshot)
                    .order_by("-adj_ec", "-due_adjusted", "debtor_name")
                )

                nav_lines = [ln for ln in nav_lines_all if _line_is_nominated(ln)]

                # Keep all lines for diagnostics if needed later
                # (used to detect suspicious "all nominated" snapshots)
                nav_snapshot._nav_lines_all = nav_lines_all
            else:
                nav_note = "No AR NAV snapshot found for this ABN/ACN + transaction_id."

        except Exception as ex:
            nav_note = f"Failed to load NAV snapshot: {ex}"
            nav_available = False

    # If NAV available, compute totals + key widget state from snapshot.meta
    nav_meta_ar = {}
    nav_totals = {
        "nominated_count": 0,
        "sum_base_due": Decimal("0"),
        "sum_excluded": Decimal("0"),
        "sum_due_adjusted": Decimal("0"),
        "sum_base_ec": Decimal("0"),
        "sum_adj_ec": Decimal("0"),
    }
    excluded_buckets = []
    adv_pct_used = None
    conc_limit_global = None

    top_debtors_adj = []  # (name, adj_ec, conc_pct, excluded)
    flags = []            # text flags

    if nav_available and nav_snapshot:
        meta_val = getattr(nav_snapshot, "meta", {}) or {}
        if isinstance(meta_val, dict):
            nav_meta_ar = meta_val.get("ar") if isinstance(meta_val.get("ar"), dict) else {}
        else:
            nav_meta_ar = {}

        excluded_buckets = nav_meta_ar.get("excluded_buckets") or []
        if not isinstance(excluded_buckets, list):
            excluded_buckets = []

        adv_pct_used = nav_meta_ar.get("advance_rate_pct", None)
        conc_limit_global = nav_meta_ar.get("concentration_limit_pct", None)

        # Totals from NOMINATED line items only (these should reflect per-row checkbox state)
        for ln in nav_lines:
            nav_totals["nominated_count"] += 1
            nav_totals["sum_base_due"] += _d(getattr(ln, "base_due", None))
            nav_totals["sum_excluded"] += _d(getattr(ln, "excluded_amount", None))
            nav_totals["sum_due_adjusted"] += _d(getattr(ln, "due_adjusted", None))
            nav_totals["sum_base_ec"] += _d(getattr(ln, "base_ec", None))
            nav_totals["sum_adj_ec"] += _d(getattr(ln, "adj_ec", None))

        # Top 5 by adj_ec concentration (post-adjust) — nominated rows only
        # Top 5 by adj_ec concentration (post-adjust) — nominated rows only
        # Show concentration haircut PER debtor (not bucket exclusion)
        top = list(nav_lines[:5])
        for ln in top:
            name = getattr(ln, "debtor_name", "") or "Unknown"
            base_ec = _d(getattr(ln, "base_ec", None))
            adj_ec = _d(getattr(ln, "adj_ec", None))
            conc_pct = _d(getattr(ln, "concentration_pct", None))

            # Exact amount excluded due to concentration limits
            conc_excl = base_ec - adj_ec
            if conc_excl < 0:
                conc_excl = Decimal("0")

            top_debtors_adj.append((name, adj_ec, conc_pct, conc_excl))
        # Flags (simple + useful)
        if nav_totals["sum_base_ec"] > 0:
            haircut = nav_totals["sum_base_ec"] - nav_totals["sum_adj_ec"]
            if haircut > 0:
                pct = (haircut / nav_totals["sum_base_ec"]) * Decimal("100")
                flags.append(f"Concentration haircut: {_money(haircut)} ({_pct(pct)})")

        if nav_totals["sum_base_due"] > 0 and nav_totals["sum_excluded"] > 0:
            excl_pct = (nav_totals["sum_excluded"] / nav_totals["sum_base_due"]) * Decimal("100")
            flags.append(f"Buckets excluded (total): {_money(nav_totals['sum_excluded'])} ({_pct(excl_pct)})")

        # any debtor with conc_pct > its limit (if you store per-row limit) — nominated rows only
        try:
            over_limit = []
            for ln in nav_lines:
                conc_pct = _d(getattr(ln, "concentration_pct", None))
                limit = _d(getattr(ln, "concentration_limit_pct", None))
                if limit > 0 and conc_pct > limit:
                    over_limit.append((getattr(ln, "debtor_name", "") or "Unknown", conc_pct, limit))
            if over_limit:
                # only show up to 3
                show = over_limit[:3]
                msg = "; ".join([f"{n} ({_pct(c)} > {_pct(l)})" for n, c, l in show])
                flags.append(f"Over concentration limit: {msg}")
        except Exception:
            pass

        # Diagnostic flag if every row in snapshot is nominated (often a save-logic issue)
        try:
            all_lines = getattr(nav_snapshot, "_nav_lines_all", []) or []
            total_lines_in_snapshot = len(all_lines)
            nominated_lines_in_snapshot = len(nav_lines)
            if total_lines_in_snapshot > 0 and nominated_lines_in_snapshot == total_lines_in_snapshot:
                flags.append(
                    "All NAVARLine rows in this snapshot are marked nominated. "
                    "If the UI now nominates one debtor at a time, verify snapshot save logic persists per-row checkbox state."
                )
        except Exception:
            pass

    # ============================================================
    # Build summary (what gets appended to Sales Notes)
    # ============================================================
    summary_lines = [
        f"[{stamp}] AR Ledger analysis for ABN={e(abn) or 'N/A'}, ACN={e(acn) or 'N/A'}, TX={e(transaction_id) or 'N/A'}",
        "",
        "RAW LEDGER (UploadedLedgerData)",
        f"- Rows matched: {count_rows:,}",
        f"- Total aged receivables (raw): ${total_aged_raw:,.2f}",
    ]
    if top5_raw_lines:
        summary_lines.append("- Top 5 debtors (raw concentration):")
        summary_lines.extend([f"  {x}" for x in top5_raw_lines])
    else:
        summary_lines.append("- Top 5 debtors (raw concentration): N/A")

    summary_lines.append("")
    summary_lines.append("NAV SNAPSHOT (Saved AR widget state)")
    if not nav_available:
        summary_lines.append(f"- {nav_note or 'NAV snapshot unavailable.'}")
    elif not nav_snapshot:
        summary_lines.append(f"- {nav_note or 'No snapshot found.'}")
    else:
        # Snapshot-level fields (from snapshot and meta)
        total_snapshot_rows = len(getattr(nav_snapshot, "_nav_lines_all", []) or [])

        summary_lines.extend([
            f"- Snapshot ID: {getattr(nav_snapshot, 'id', 'N/A')}",
            f"- Snapshot created_at: {getattr(nav_snapshot, 'created_at', 'N/A')}",
            f"- Advance rate (meta): {adv_pct_used if adv_pct_used is not None else 'N/A'}%",
            f"- Global concentration limit (meta): {conc_limit_global if conc_limit_global is not None else 'N/A'}%",
            f"- Excluded buckets (meta): {', '.join(excluded_buckets) if excluded_buckets else 'None'}",
            "",
            "EC / ELIGIBLE COLLATERAL (nominated NAVARLine rows only)",
            f"- Snapshot rows (all): {total_snapshot_rows:,}",
            f"- Nominated debtors saved: {nav_totals['nominated_count']:,}",
            f"- Base due (pre-exclusions): {_money(nav_totals['sum_base_due'])}",
            f"- Excluded amount (bucket toggles impact): {_money(nav_totals['sum_excluded'])}",
            f"- Due adjusted (drives EC): {_money(nav_totals['sum_due_adjusted'])}",
            f"- Base EC (pre-concentration): {_money(nav_totals['sum_base_ec'])}",
            f"- Adj EC (post-concentration): {_money(nav_totals['sum_adj_ec'])}",
        ])

        if flags:
            summary_lines.append("")
            summary_lines.append("Flags")
            summary_lines.extend([f"- {f}" for f in flags])

        if top_debtors_adj:
            summary_lines.append("")
            summary_lines.append("Top debtors by Adj EC (post-concentration)")
            for name, adj_ec, conc_pct, conc_excl in top_debtors_adj:
                summary_lines.append(
                    f"- {name}: Adj EC {_money(adj_ec)} | Conc {_pct(conc_pct)} | "
                    f"Concentration Excluded {_money(conc_excl)}"
                )

        # Optional: compare raw total vs due_adjusted
        try:
            raw_dec = _d(total_aged_raw)
            if raw_dec > 0:
                delta = raw_dec - nav_totals["sum_due_adjusted"]
                summary_lines.append("")
                summary_lines.append("Cross-check")
                summary_lines.append(f"- Raw total aged vs Due adjusted delta: {_money(delta)}")
        except Exception:
            pass

    summary = "\n".join(summary_lines)

    # ============================================================
    # Table HTML (optional; can still return it)
    # ============================================================
    table_html_parts = []
    table_html_parts.append(
        "<table border='1' cellpadding='6' cellspacing='0'>"
        "<thead><tr><th colspan='2'>AR Ledger Summary</th></tr></thead><tbody>"
        f"<tr><td>Rows matched (raw)</td><td>{count_rows:,}</td></tr>"
        f"<tr><td>Total aged receivables (raw)</td><td>${total_aged_raw:,.2f}</td></tr>"
        "</tbody></table>"
    )

    if nav_available and nav_snapshot:

        table_html_parts.append(
            "<br/>"
            "<table border='1' cellpadding='6' cellspacing='0'>"
            "<thead><tr><th colspan='2'>NAV Snapshot (AR)</th></tr></thead><tbody>"
            f"<tr><td>Snapshot ID</td><td>{html.escape(str(getattr(nav_snapshot, 'id', '')))}</td></tr>"
            f"<tr><td>Nominated debtors</td><td>{nav_totals['nominated_count']:,}</td></tr>"
            f"<tr><td>Base due</td><td>{_money(nav_totals['sum_base_due'])}</td></tr>"
            f"<tr><td>Excluded amount</td><td>{_money(nav_totals['sum_excluded'])}</td></tr>"
            f"<tr><td>Due adjusted</td><td>{_money(nav_totals['sum_due_adjusted'])}</td></tr>"
            f"<tr><td>Base EC</td><td>{_money(nav_totals['sum_base_ec'])}</td></tr>"
            f"<tr><td>Adj EC</td><td>{_money(nav_totals['sum_adj_ec'])}</td></tr>"
            "</tbody></table>"
        )

        if top_debtors_adj:
            rows = "".join(
                "<tr>"
                f"<td>{html.escape(str(name))}</td>"
                f"<td>{_money(adj_ec)}</td>"
                f"<td>{_pct(conc_pct)}</td>"
                f"<td>{_money(conc_excl)}</td>"
                "</tr>"
                for name, adj_ec, conc_pct, conc_excl in top_debtors_adj
            )
            table_html_parts.append(
                "<br/>"
                "<table border='1' cellpadding='6' cellspacing='0'>"
                "<thead><tr>"
                "<th>Debtor</th><th>Adj EC</th><th>Conc %</th><th>Conc Excluded</th>"                "</tr></thead>"
                f"<tbody>{rows}</tbody></table>"
            )
    elif nav_note:
        table_html_parts.append(
            "<br/>"
            "<div><em>"
            f"{html.escape(nav_note)}"
            "</em></div>"
        )

    table_html = "".join(table_html_parts)

    log.info(
        "[AR] run_analysis done raw_rows=%d raw_total=%.2f nav=%s",
        count_rows,
        total_aged_raw,
        "yes" if (nav_available and nav_snapshot) else "no",
    )
    return summary, table_html
