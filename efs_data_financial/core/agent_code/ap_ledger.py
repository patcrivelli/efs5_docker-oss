# efs_data_financial/core/agent_code/ap_ledger.py
import logging
import html
from datetime import datetime

from django.apps import apps
from django.core.exceptions import ImproperlyConfigured

log = logging.getLogger(__name__)


def _get_uploaded_ap_model():
    """
    Resolve UploadAPLedgerData robustly regardless of app label.
    """
    for label in ("efs_data_financial", "efs_data_financial.core", "core", "efs_data"):
        try:
            model = apps.get_model(label, "UploadAPLedgerData")
            if model is not None:
                return model
        except LookupError:
            pass

    for m in apps.get_models():
        if m.__name__ == "UploadAPLedgerData":
            return m

    labels = sorted({m._meta.app_label for m in apps.get_models()})
    raise ImproperlyConfigured(
        "Could not resolve model UploadAPLedgerData. "
        "Ensure the defining app is in INSTALLED_APPS and migrations are applied. "
        f"Known app labels: {labels}"
    )


def _to_number(txt):
    """
    Parse currency-like strings: '$', ',', spaces, parentheses for negatives.
    """
    if not txt:
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


def run_analysis(abn=None, acn=None, transaction_id=None):
    """
    Accounts Payable analysis.
    Returns (summary:str, table_html:str). Safe to json.dumps and render on the client.
    Mirrors ar_ledger.py but aggregates by 'creditor' and uses AP bucket fields.
    """
    ident = abn or acn or ""
    ident_type = "ABN" if abn else ("ACN" if acn else "ID")

    log.info("[AP] run_analysis start %s=%s tx=%s", ident_type, ident, transaction_id)
    print(f"[AP] run_analysis: {ident_type}={ident} tx={transaction_id}")

    e = lambda s: html.escape(str(s or ""), quote=True)

    # ---- fetch data ----
    UploadAPLedgerData = _get_uploaded_ap_model()
    qs = UploadAPLedgerData.objects.all()
    if abn:
        qs = qs.filter(abn=abn)
    elif acn:
        qs = qs.filter(acn=acn)
    if transaction_id:
        qs = qs.filter(transaction_id=transaction_id)

    # Totals + per-creditor aggregation (use 'aged_payables' as primary)
    total_aged = 0.0
    count_rows = 0
    per_creditor = {}  # creditor -> sum aged_payables

    # also compute bucket totals (optional in summary/table)
    t_curr = t_0_30 = t_31_60 = t_61_90 = t_90p = 0.0

    for row in qs.only("creditor", "aged_payables", "days_0_30", "days_31_60", "days_61_90", "days_90_plus"):
        amt = _to_number(row.aged_payables)
        creditor = (row.creditor or "Unknown").strip() or "Unknown"
        per_creditor[creditor] = per_creditor.get(creditor, 0.0) + amt
        total_aged += amt
        count_rows += 1

        t_curr  += _to_number(row.aged_payables)  # treat 'aged_payables' as current headline total (to mirror AR)
        t_0_30  += _to_number(row.days_0_30)
        t_31_60 += _to_number(row.days_31_60)
        t_61_90 += _to_number(row.days_61_90)
        t_90p   += _to_number(row.days_90_plus)

    # Top 5 by concentration (share of total)
    top5_lines = []
    top5_rows = []
    if total_aged > 0:
        ranked = sorted(per_creditor.items(), key=lambda kv: kv[1], reverse=True)[:5]
        for creditor, amount in ranked:
            share = (amount / total_aged) * 100.0
            line = f"- {creditor}: {share:.2f}% (${amount:,.2f})"
            top5_lines.append(line)
            top5_rows.append((creditor, amount, share))

    stamp = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")

    # ---- Summary written into Sales Notes ----
    lines = [
        f"[{stamp}] AP Ledger analysis for "
        f"ABN={e(abn) or 'N/A'}, ACN={e(acn) or 'N/A'}, TX={e(transaction_id) or 'N/A'}",
        f"Rows matched: {count_rows:,}",
        f"Total aged payables: ${total_aged:,.2f}",
    ]
    if top5_lines:
        lines.append("Top 5 creditors by concentration:")
        lines.extend(top5_lines)
    else:
        lines.append("Top 5 creditors by concentration: N/A (no data).")

    summary = "\n".join(lines)

    # ---- Minimal HTML table (not used by your UI, but included) ----
    table_html = (
        "<table border='1' cellpadding='6' cellspacing='0'>"
        "<thead><tr>"
        "<th>Rows Matched</th><th>Total Aged Payables</th>"
        "<th>0–30</th><th>31–60</th><th>61–90</th><th>90+</th>"
        "</tr></thead><tbody>"
        f"<tr><td>{count_rows:,}</td>"
        f"<td>${total_aged:,.2f}</td>"
        f"<td>${t_0_30:,.2f}</td>"
        f"<td>${t_31_60:,.2f}</td>"
        f"<td>${t_61_90:,.2f}</td>"
        f"<td>${t_90p:,.2f}</td></tr>"
        "</tbody></table>"
    )

    if top5_rows:
        rows = "".join(
            f"<tr><td>{html.escape(c)}</td><td>${amt:,.2f}</td><td>{share:.2f}%</td></tr>"
            for c, amt, share in top5_rows
        )
        table_html += (
            "<br/><table border='1' cellpadding='6' cellspacing='0'>"
            "<thead><tr><th>Creditor</th><th>Amount</th><th>Concentration</th></tr></thead>"
            f"<tbody>{rows}</tbody></table>"
        )

    log.info("[AP] run_analysis done rows=%d total=%.2f", count_rows, total_aged)
    return summary, table_html
