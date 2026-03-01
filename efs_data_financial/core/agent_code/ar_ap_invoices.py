"""
AR/AP Invoice analysis agent

Expected entrypoint:
    run_analysis(abn=None, acn=None, transaction_id=None) -> (summary: str, table_html: str)

What it does:
- Pulls data from:
    - InvoiceData (API/source invoice table)
    - InvoiceDataUploaded (uploaded AR invoice/payment history)
    - AP_InvoiceDataUploaded (uploaded AP invoice/payment history)
- Filters by transaction_id and/or ABN/ACN
- Analyses CLOSED invoices (and similar settled states)
- Computes timing metrics (issue/funded -> paid, paid vs due date)
- Aggregates by counterparty:
    - debtor for AR
    - creditor for AP
- Aggregates by transaction_id across AR/AP history
- Flags common anomalies / mismatches for AR where API row and uploaded row align by (transaction_id, inv_number)

This is designed to be concatenated later with bank transaction analysis to compare historical alignment.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation
from html import escape
from typing import Any, Dict, Iterable, List, Optional, Tuple

from django.apps import apps
from django.db.models import Q


# -----------------------------
# Config / constants
# -----------------------------

CLOSED_STATES = {
    "closed",
    "paid",
    "settled",
    "complete",
    "completed",
}

MONEY_ZERO = Decimal("0.00")
DISPLAY_LIMIT_ANOMALIES = 100
DISPLAY_LIMIT_TXN_ROWS = 200
DISPLAY_LIMIT_PARTY_ROWS = 200


# -----------------------------
# Helpers
# -----------------------------

def _to_str(v: Any) -> str:
    return "" if v is None else str(v)


def _norm_str(v: Any) -> str:
    return _to_str(v).strip()


def _norm_lower(v: Any) -> str:
    return _norm_str(v).lower()


def _to_decimal(v: Any) -> Decimal:
    if v is None or v == "":
        return MONEY_ZERO
    if isinstance(v, Decimal):
        return v
    try:
        return Decimal(str(v))
    except (InvalidOperation, TypeError, ValueError):
        return MONEY_ZERO


def _money(v: Any) -> str:
    d = _to_decimal(v)
    return f"{d:,.2f}"


def _date_str(v: Any) -> str:
    if not v:
        return ""
    try:
        return v.strftime("%Y-%m-%d")
    except Exception:
        return str(v)


def _days_between(d1: Optional[date], d2: Optional[date]) -> Optional[int]:
    if not d1 or not d2:
        return None
    try:
        return (d2 - d1).days
    except Exception:
        return None


def _avg(nums: List[int | float]) -> Optional[float]:
    if not nums:
        return None
    return sum(nums) / len(nums)


def _fmt_num(v: Any) -> str:
    if v is None:
        return ""
    if isinstance(v, float):
        return f"{v:.2f}"
    return str(v)


def _html_table(title: str, rows: List[Dict[str, Any]], columns: List[Tuple[str, str]]) -> str:
    """
    columns: [(key, heading), ...]
    """
    if not rows:
        return f"""
        <div style="margin-bottom:16px;">
          <h4 style="margin:0 0 8px 0;">{escape(title)}</h4>
          <div style="color:#666;">No data</div>
        </div>
        """

    thead = "".join(f"<th>{escape(h)}</th>" for _, h in columns)
    body_rows = []
    for r in rows:
        tds = []
        for key, _ in columns:
            val = r.get(key, "")
            if isinstance(val, Decimal):
                val = _money(val)
            elif isinstance(val, float):
                val = f"{val:.2f}"
            elif isinstance(val, (int, str)):
                val = str(val)
            elif val is None:
                val = ""
            else:
                val = str(val)
            tds.append(f"<td>{escape(val)}</td>")
        body_rows.append("<tr>" + "".join(tds) + "</tr>")

    return f"""
    <div style="margin-bottom:20px;">
      <h4 style="margin:0 0 8px 0;">{escape(title)}</h4>
      <div style="overflow:auto; border:1px solid #ddd; border-radius:6px;">
        <table style="width:100%; border-collapse:collapse; font-size:12px;">
          <thead>
            <tr style="background:#f7f7f7;">{thead}</tr>
          </thead>
          <tbody>
            {''.join(body_rows)}
          </tbody>
        </table>
      </div>
    </div>
    """


def _find_model_by_name(model_name: str):
    """
    Finds a Django model class by class name across installed apps.
    Useful because this file is dynamically loaded and shouldn't hardcode app labels.
    """
    matches = []
    for m in apps.get_models():
        if m.__name__ == model_name:
            matches.append(m)

    if not matches:
        raise LookupError(f"Model '{model_name}' not found in installed apps.")

    # Prefer exact expected db_table if present (helps if duplicate class names exist)
    expected_tables = {
        "InvoiceData": "efs_financial_invoicedata",
        "InvoiceDataUploaded": "efs_financial_invoicedata_uploaded",
        "AP_InvoiceDataUploaded": "efs_financial_ap_invoicedata_uploaded",
    }
    expected = expected_tables.get(model_name)
    if expected:
        for m in matches:
            try:
                if m._meta.db_table == expected:
                    return m
            except Exception:
                pass

    # fallback to first match
    return matches[0]


def _apply_filters(qs, abn: Optional[str], acn: Optional[str], transaction_id: Optional[str]):
    """
    Filter by transaction_id if provided, and/or ABN/ACN.
    Uses OR for ABN/ACN to avoid excluding rows when one identifier is blank.
    """
    if transaction_id:
        qs = qs.filter(transaction_id=transaction_id)

    id_q = Q()
    has_id_filter = False
    if abn:
        id_q |= Q(abn=abn)
        has_id_filter = True
    if acn:
        id_q |= Q(acn=acn)
        has_id_filter = True

    if has_id_filter:
        qs = qs.filter(id_q)

    return qs


def _get_field(obj: Any, name: str, default=None):
    return getattr(obj, name, default)


def _is_closed_state(state_value: Any) -> bool:
    return _norm_lower(state_value) in CLOSED_STATES


def _compute_closed_metrics(rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Compute timing / lateness metrics for a single side (AR or AP) from uploaded rows.
    """
    closed_rows = [r for r in rows if r.get("is_closed")]

    days_to_pay_vals: List[int] = []
    days_past_due_vals: List[int] = []
    late_closed = 0
    closed_with_nonzero_amount_due = 0

    for r in closed_rows:
        d2p = _days_between(r.get("date_funded"), r.get("date_paid"))
        dpd = _days_between(r.get("due_date"), r.get("date_paid"))

        if d2p is not None:
            days_to_pay_vals.append(d2p)

        if dpd is not None:
            days_past_due_vals.append(dpd)
            if dpd > 0:
                late_closed += 1

        if _to_decimal(r.get("amount_due")) > MONEY_ZERO:
            closed_with_nonzero_amount_due += 1

    closed_count = len(closed_rows)
    late_rate = (late_closed / closed_count * 100.0) if closed_count else 0.0

    return {
        "closed_count": closed_count,
        "days_to_pay_vals": days_to_pay_vals,
        "days_past_due_vals": days_past_due_vals,
        "avg_days_to_pay": _avg(days_to_pay_vals),
        "avg_days_past_due": _avg(days_past_due_vals),
        "late_closed": late_closed,
        "late_rate": late_rate,
        "closed_with_nonzero_amount_due": closed_with_nonzero_amount_due,
    }

# -----------------------------
# Normalization
# -----------------------------

def _normalize_ar_api(obj) -> Dict[str, Any]:
    return {
        "source": "AR_API",
        "side": "AR",
        "transaction_id": _norm_str(_get_field(obj, "transaction_id")),
        "inv_number": _norm_str(_get_field(obj, "inv_number")),
        "abn": _norm_str(_get_field(obj, "abn")),
        "acn": _norm_str(_get_field(obj, "acn")),
        "name": _norm_str(_get_field(obj, "name")),
        "counterparty": _norm_str(_get_field(obj, "debtor")),
        "counterparty_type": "debtor",
        "date_funded": _get_field(obj, "date_funded"),
        "due_date": _get_field(obj, "due_date"),
        "date_paid": None,
        "invoice_state": "",
        "amount_funded": _to_decimal(_get_field(obj, "amount_funded")),
        "amount_due": _to_decimal(_get_field(obj, "amount_due")),
        "face_value": _to_decimal(_get_field(obj, "face_value")),
        "discount_percentage": _to_decimal(_get_field(obj, "discount_percentage")),
        "approve_reject": _norm_str(_get_field(obj, "approve_reject")),
        "is_closed": False,
    }


def _normalize_ar_uploaded(obj) -> Dict[str, Any]:
    state = _norm_str(_get_field(obj, "invoice_state"))
    return {
        "source": "AR_UPLOADED",
        "side": "AR",
        "transaction_id": _norm_str(_get_field(obj, "transaction_id")),
        "inv_number": _norm_str(_get_field(obj, "inv_number")),
        "abn": _norm_str(_get_field(obj, "abn")),
        "acn": _norm_str(_get_field(obj, "acn")),
        "name": _norm_str(_get_field(obj, "name")),
        "counterparty": _norm_str(_get_field(obj, "debtor")),
        "counterparty_type": "debtor",
        "date_funded": _get_field(obj, "date_funded"),
        "due_date": _get_field(obj, "due_date"),
        "date_paid": _get_field(obj, "date_paid"),
        "invoice_state": state,
        "amount_funded": _to_decimal(_get_field(obj, "amount_funded")),
        "amount_due": _to_decimal(_get_field(obj, "amount_due")),
        "face_value": _to_decimal(_get_field(obj, "face_value")),
        "discount_percentage": _to_decimal(_get_field(obj, "discount_percentage")),
        "approve_reject": _norm_str(_get_field(obj, "approve_reject")),
        "is_closed": _is_closed_state(state),
    }


def _normalize_ap_uploaded(obj) -> Dict[str, Any]:
    state = _norm_str(_get_field(obj, "invoice_state"))
    return {
        "source": "AP_UPLOADED",
        "side": "AP",
        "transaction_id": _norm_str(_get_field(obj, "transaction_id")),
        "inv_number": _norm_str(_get_field(obj, "inv_number")),
        "abn": _norm_str(_get_field(obj, "abn")),
        "acn": _norm_str(_get_field(obj, "acn")),
        "name": _norm_str(_get_field(obj, "name")),
        "counterparty": _norm_str(_get_field(obj, "creditor")),
        "counterparty_type": "creditor",
        "date_funded": _get_field(obj, "date_funded"),
        "due_date": _get_field(obj, "due_date"),
        "date_paid": _get_field(obj, "date_paid"),
        "invoice_state": state,
        "amount_funded": _to_decimal(_get_field(obj, "amount_funded")),
        "amount_due": _to_decimal(_get_field(obj, "amount_due")),
        "face_value": _to_decimal(_get_field(obj, "face_value")),
        "discount_percentage": _to_decimal(_get_field(obj, "discount_percentage")),
        "approve_reject": _norm_str(_get_field(obj, "approve_reject")),
        "is_closed": _is_closed_state(state),
    }


# -----------------------------
# Core analysis
# -----------------------------

def run_analysis(abn=None, acn=None, transaction_id=None):
    # 1) Resolve models dynamically
    InvoiceData = _find_model_by_name("InvoiceData")
    InvoiceDataUploaded = _find_model_by_name("InvoiceDataUploaded")
    AP_InvoiceDataUploaded = _find_model_by_name("AP_InvoiceDataUploaded")

    # 2) Query
    ar_api_qs = _apply_filters(InvoiceData.objects.all(), abn, acn, transaction_id)
    ar_up_qs = _apply_filters(InvoiceDataUploaded.objects.all(), abn, acn, transaction_id)
    ap_up_qs = _apply_filters(AP_InvoiceDataUploaded.objects.all(), abn, acn, transaction_id)

    # Orderings help historical reads
    try:
        ar_api_qs = ar_api_qs.order_by("transaction_id", "inv_number", "date_funded")
        ar_up_qs = ar_up_qs.order_by("transaction_id", "inv_number", "date_funded", "date_paid")
        ap_up_qs = ap_up_qs.order_by("transaction_id", "inv_number", "date_funded", "date_paid")
    except Exception:
        pass

    ar_api_rows = [_normalize_ar_api(x) for x in ar_api_qs]
    ar_up_rows = [_normalize_ar_uploaded(x) for x in ar_up_qs]
    ap_up_rows = [_normalize_ap_uploaded(x) for x in ap_up_qs]

    if not (ar_api_rows or ar_up_rows or ap_up_rows):
        summary = "No AR/AP invoice data found for the supplied filters."
        table_html = _html_table("AR/AP Invoices", [], [("message", "Message")])
        return summary, table_html

    # 3) Build indexes for AR API vs AR uploaded reconciliation
    ar_api_by_txn_inv: Dict[Tuple[str, str], Dict[str, Any]] = {}
    ar_api_by_inv: Dict[str, Dict[str, Any]] = {}

    for r in ar_api_rows:
        txn = r["transaction_id"]
        inv = r["inv_number"]
        if txn and inv and (txn, inv) not in ar_api_by_txn_inv:
            ar_api_by_txn_inv[(txn, inv)] = r
        if inv and inv not in ar_api_by_inv:
            ar_api_by_inv[inv] = r

    # 4) Aggregations
    # By party (debtor/creditor)
    party_agg: Dict[Tuple[str, str], Dict[str, Any]] = defaultdict(lambda: {
        "side": "",
        "counterparty_type": "",
        "counterparty": "",
        "invoice_count": 0,
        "closed_count": 0,
        "open_count": 0,
        "total_face_value": MONEY_ZERO,
        "total_amount_funded": MONEY_ZERO,
        "total_amount_due": MONEY_ZERO,
        "closed_with_balance_count": 0,
        "late_payment_count": 0,
        "on_time_or_early_count": 0,
        "days_to_pay_values": [],
        "days_past_due_values": [],
    })

    # By transaction_id (combined AR/AP)
    txn_agg: Dict[str, Dict[str, Any]] = defaultdict(lambda: {
        "transaction_id": "",
        "ar_invoice_count": 0,
        "ap_invoice_count": 0,
        "ar_closed_count": 0,
        "ap_closed_count": 0,
        "total_face_value_ar": MONEY_ZERO,
        "total_face_value_ap": MONEY_ZERO,
        "total_amount_due_ar": MONEY_ZERO,
        "total_amount_due_ap": MONEY_ZERO,
        "first_issue_date": None,
        "latest_due_date": None,
        "latest_payment_date": None,
        "days_to_pay_values": [],
        "counterparties": set(),
    })

    anomalies: List[Dict[str, Any]] = []
    closed_invoice_timeline_rows: List[Dict[str, Any]] = []

    def _update_dates_minmax(bucket: Dict[str, Any], row: Dict[str, Any]):
        df = row.get("date_funded")
        dd = row.get("due_date")
        dp = row.get("date_paid")
        if df and (bucket["first_issue_date"] is None or df < bucket["first_issue_date"]):
            bucket["first_issue_date"] = df
        if dd and (bucket["latest_due_date"] is None or dd > bucket["latest_due_date"]):
            bucket["latest_due_date"] = dd
        if dp and (bucket["latest_payment_date"] is None or dp > bucket["latest_payment_date"]):
            bucket["latest_payment_date"] = dp

    def _process_uploaded_row(row: Dict[str, Any], api_match: Optional[Dict[str, Any]] = None):
        # Party aggregation
        pkey = (row["side"], row["counterparty"] or "(blank)")
        p = party_agg[pkey]
        p["side"] = row["side"]
        p["counterparty_type"] = row["counterparty_type"]
        p["counterparty"] = row["counterparty"] or "(blank)"
        p["invoice_count"] += 1
        p["closed_count"] += 1 if row["is_closed"] else 0
        p["open_count"] += 0 if row["is_closed"] else 1
        p["total_face_value"] += row["face_value"]
        p["total_amount_funded"] += row["amount_funded"]
        p["total_amount_due"] += row["amount_due"]

        # Transaction aggregation
        txid = row["transaction_id"] or "(blank)"
        t = txn_agg[txid]
        t["transaction_id"] = txid
        if row["side"] == "AR":
            t["ar_invoice_count"] += 1
            t["ar_closed_count"] += 1 if row["is_closed"] else 0
            t["total_face_value_ar"] += row["face_value"]
            t["total_amount_due_ar"] += row["amount_due"]
        else:
            t["ap_invoice_count"] += 1
            t["ap_closed_count"] += 1 if row["is_closed"] else 0
            t["total_face_value_ap"] += row["face_value"]
            t["total_amount_due_ap"] += row["amount_due"]

        if row["counterparty"]:
            t["counterparties"].add(row["counterparty"])
        _update_dates_minmax(t, row)

        # Closed invoice timing analysis
        if row["is_closed"]:
            days_to_pay = _days_between(row.get("date_funded"), row.get("date_paid"))
            days_past_due = _days_between(row.get("due_date"), row.get("date_paid"))

            if days_to_pay is not None:
                p["days_to_pay_values"].append(days_to_pay)
                t["days_to_pay_values"].append(days_to_pay)

            if days_past_due is not None:
                p["days_past_due_values"].append(days_past_due)
                if days_past_due > 0:
                    p["late_payment_count"] += 1
                else:
                    p["on_time_or_early_count"] += 1

            closed_with_balance = row["amount_due"] > MONEY_ZERO
            if closed_with_balance:
                p["closed_with_balance_count"] += 1

            # AR API vs uploaded reconciliation
            issue_date_delta = None
            due_date_delta = None
            face_value_delta = None
            funded_delta = None
            amount_due_delta = None
            api_match_found = bool(api_match)

            if api_match:
                issue_date_delta = _days_between(api_match.get("date_funded"), row.get("date_funded"))
                due_date_delta = _days_between(api_match.get("due_date"), row.get("due_date"))
                face_value_delta = row["face_value"] - api_match["face_value"]
                funded_delta = row["amount_funded"] - api_match["amount_funded"]
                amount_due_delta = row["amount_due"] - api_match["amount_due"]

            closed_invoice_timeline_rows.append({
                "side": row["side"],
                "transaction_id": row["transaction_id"] or "",
                "inv_number": row["inv_number"] or "",
                "counterparty": row["counterparty"] or "",
                "invoice_state": row["invoice_state"] or "",
                "issue_date": _date_str(row.get("date_funded")),
                "due_date": _date_str(row.get("due_date")),
                "date_paid": _date_str(row.get("date_paid")),
                "days_to_pay": days_to_pay if days_to_pay is not None else "",
                "days_past_due": days_past_due if days_past_due is not None else "",
                "face_value": _money(row["face_value"]),
                "amount_funded": _money(row["amount_funded"]),
                "amount_due_at_close": _money(row["amount_due"]),
                "api_match": "Yes" if api_match_found else ("N/A" if row["side"] == "AP" else "No"),
                "api_issue_date_delta_days": issue_date_delta if issue_date_delta is not None else "",
                "api_due_date_delta_days": due_date_delta if due_date_delta is not None else "",
                "api_face_value_delta": _money(face_value_delta) if face_value_delta is not None else "",
                "api_amount_funded_delta": _money(funded_delta) if funded_delta is not None else "",
                "api_amount_due_delta": _money(amount_due_delta) if amount_due_delta is not None else "",
            })

            # Anomaly detection (for exception review)
            anomaly_reasons = []
            if closed_with_balance:
                anomaly_reasons.append("closed_with_balance")
            if days_past_due is not None and days_past_due > 0:
                anomaly_reasons.append("paid_late")
            if api_match_found and issue_date_delta not in (None, 0):
                anomaly_reasons.append("issue_date_mismatch")
            if api_match_found and due_date_delta not in (None, 0):
                anomaly_reasons.append("due_date_mismatch")
            if api_match_found and face_value_delta is not None and face_value_delta != MONEY_ZERO:
                anomaly_reasons.append("face_value_mismatch")
            if api_match_found and funded_delta is not None and funded_delta != MONEY_ZERO:
                anomaly_reasons.append("amount_funded_mismatch")

            if anomaly_reasons:
                anomalies.append({
                    "side": row["side"],
                    "transaction_id": row["transaction_id"] or "",
                    "inv_number": row["inv_number"] or "",
                    "counterparty": row["counterparty"] or "",
                    "invoice_state": row["invoice_state"] or "",
                    "issue_date": _date_str(row.get("date_funded")),
                    "due_date": _date_str(row.get("due_date")),
                    "date_paid": _date_str(row.get("date_paid")),
                    "days_to_pay": days_to_pay if days_to_pay is not None else "",
                    "days_past_due": days_past_due if days_past_due is not None else "",
                    "amount_due_at_close": _money(row["amount_due"]),
                    "reasons": ", ".join(anomaly_reasons),
                })

    # Process AR uploaded rows (with optional API matching)
    for r in ar_up_rows:
        api_match = None
        txn = r["transaction_id"]
        inv = r["inv_number"]
        if txn and inv:
            api_match = ar_api_by_txn_inv.get((txn, inv))
        if api_match is None and inv:
            api_match = ar_api_by_inv.get(inv)
        _process_uploaded_row(r, api_match=api_match)

    # Process AP uploaded rows (no API source table provided for AP)
    for r in ap_up_rows:
        _process_uploaded_row(r, api_match=None)

    # 5) Prepare derived summary tables
    party_rows = []
    for _, p in party_agg.items():
        avg_days_to_pay = _avg(p["days_to_pay_values"])
        avg_days_past_due = _avg(p["days_past_due_values"])
        party_rows.append({
            "side": p["side"],
            "counterparty_type": p["counterparty_type"],
            "counterparty": p["counterparty"],
            "invoice_count": p["invoice_count"],
            "closed_count": p["closed_count"],
            "open_count": p["open_count"],
            "total_face_value": p["total_face_value"],
            "total_amount_funded": p["total_amount_funded"],
            "total_amount_due": p["total_amount_due"],
            "closed_with_balance_count": p["closed_with_balance_count"],
            "late_payment_count": p["late_payment_count"],
            "on_time_or_early_count": p["on_time_or_early_count"],
            "avg_days_to_pay": round(avg_days_to_pay, 2) if avg_days_to_pay is not None else "",
            "avg_days_past_due": round(avg_days_past_due, 2) if avg_days_past_due is not None else "",
        })

    party_rows.sort(
        key=lambda x: (
            x.get("side", ""),
            -int(x.get("invoice_count", 0) or 0),
            x.get("counterparty", "")
        )
    )

    txn_rows = []
    for txid, t in txn_agg.items():
        avg_days_to_pay = _avg(t["days_to_pay_values"])
        txn_rows.append({
            "transaction_id": txid,
            "ar_invoice_count": t["ar_invoice_count"],
            "ap_invoice_count": t["ap_invoice_count"],
            "ar_closed_count": t["ar_closed_count"],
            "ap_closed_count": t["ap_closed_count"],
            "total_face_value_ar": t["total_face_value_ar"],
            "total_face_value_ap": t["total_face_value_ap"],
            "total_amount_due_ar": t["total_amount_due_ar"],
            "total_amount_due_ap": t["total_amount_due_ap"],
            "first_issue_date": _date_str(t["first_issue_date"]),
            "latest_due_date": _date_str(t["latest_due_date"]),
            "latest_payment_date": _date_str(t["latest_payment_date"]),
            "avg_days_to_pay_closed": round(avg_days_to_pay, 2) if avg_days_to_pay is not None else "",
            "counterparty_count": len(t["counterparties"]),
            "counterparties_sample": ", ".join(sorted(list(t["counterparties"]))[:5]),
        })

    txn_rows.sort(
        key=lambda x: (
            -(int(x.get("ar_invoice_count", 0) or 0) + int(x.get("ap_invoice_count", 0) or 0)),
            x.get("transaction_id", "")
        )
    )

    # Timeline rows: sort newest paid date first, then due date
    def _sort_key_timeline(x):
        return (x.get("date_paid", ""), x.get("due_date", ""), x.get("transaction_id", ""), x.get("inv_number", ""))
    closed_invoice_timeline_rows.sort(key=_sort_key_timeline, reverse=True)

    anomalies.sort(
        key=lambda x: (
            x.get("side", ""),
            x.get("transaction_id", ""),
            x.get("inv_number", "")
        )
    )

        # 6) Compute side-specific + overall summary metrics (CLEARLY SEPARATED)
    total_ar_api = len(ar_api_rows)
    total_ar_uploaded = len(ar_up_rows)
    total_ap_uploaded = len(ap_up_rows)

    ar_metrics = _compute_closed_metrics(ar_up_rows)
    ap_metrics = _compute_closed_metrics(ap_up_rows)

    total_closed = ar_metrics["closed_count"] + ap_metrics["closed_count"]
    all_days_to_pay = ar_metrics["days_to_pay_vals"] + ap_metrics["days_to_pay_vals"]
    all_days_past_due = ar_metrics["days_past_due_vals"] + ap_metrics["days_past_due_vals"]

    avg_days_to_pay_all = _avg(all_days_to_pay)
    avg_days_past_due_all = _avg(all_days_past_due)

    late_closed_total = ar_metrics["late_closed"] + ap_metrics["late_closed"]
    closed_with_balance_total = (
        ar_metrics["closed_with_nonzero_amount_due"] + ap_metrics["closed_with_nonzero_amount_due"]
    )

    # Split outputs by side for clarity
    party_rows_ar = [x for x in party_rows if x.get("side") == "AR"]
    party_rows_ap = [x for x in party_rows if x.get("side") == "AP"]

    txn_rows_ar = [x for x in txn_rows if int(x.get("ar_invoice_count", 0) or 0) > 0]
    txn_rows_ap = [x for x in txn_rows if int(x.get("ap_invoice_count", 0) or 0) > 0]

    timeline_rows_ar = [x for x in closed_invoice_timeline_rows if x.get("side") == "AR"]
    timeline_rows_ap = [x for x in closed_invoice_timeline_rows if x.get("side") == "AP"]

    anomalies_ar = [x for x in anomalies if x.get("side") == "AR"]
    anomalies_ap = [x for x in anomalies if x.get("side") == "AP"]

    # Top counterparties (separate)
    top_ar = party_rows_ar[:3]
    top_ap = party_rows_ap[:3]

    # 7) Build summary string (MULTI-LINE + SEPARATE AR vs AP)
    summary_lines = []
    scope_parts = []
    if abn:
        scope_parts.append(f"ABN={abn}")
    if acn:
        scope_parts.append(f"ACN={acn}")
    if transaction_id:
        scope_parts.append(f"transaction_id={transaction_id}")
    scope_text = ", ".join(scope_parts) if scope_parts else "no filters"

    summary_lines.append(f"AR/AP Invoice history analysis ({scope_text})")
    summary_lines.append("")

    # --- AR SECTION ---
    summary_lines.append("AR (Accounts Receivable)")
    summary_lines.append(
        f"- Rows loaded: AR API={total_ar_api}, AR Uploaded={total_ar_uploaded}."
    )
    summary_lines.append(
        f"- Closed invoices analysed: {ar_metrics['closed_count']}."
    )
    if ar_metrics["avg_days_to_pay"] is not None:
        summary_lines.append(
            f"- Average days issue/funded -> paid (closed AR): {ar_metrics['avg_days_to_pay']:.2f} days."
        )
    if ar_metrics["avg_days_past_due"] is not None:
        summary_lines.append(
            f"- Average payment timing vs due date (closed AR): {ar_metrics['avg_days_past_due']:.2f} days (positive = late)."
        )
    summary_lines.append(
        f"- Late closed AR invoices: {ar_metrics['late_closed']} ({ar_metrics['late_rate']:.2f}%)."
    )
    summary_lines.append(
        f"- Closed AR invoices with non-zero stored amount_due: {ar_metrics['closed_with_nonzero_amount_due']}."
    )
    summary_lines.append(
        f"- AR exceptions/anomalies flagged: {len(anomalies_ar)}."
    )

    if top_ar:
        ar_top_text = "; ".join(
            f"{r['counterparty']} ({r['invoice_count']} inv, face={_money(r['total_face_value'])})"
            for r in top_ar
        )
        summary_lines.append(f"- Top AR debtors: {ar_top_text}.")
    else:
        summary_lines.append("- Top AR debtors: None.")

    summary_lines.append("")

    # --- AP SECTION ---
    summary_lines.append("AP (Accounts Payable)")
    summary_lines.append(
        f"- Rows loaded: AP Uploaded={total_ap_uploaded}."
    )
    summary_lines.append(
        f"- Closed invoices analysed: {ap_metrics['closed_count']}."
    )
    if ap_metrics["avg_days_to_pay"] is not None:
        summary_lines.append(
            f"- Average days issue/funded -> paid (closed AP): {ap_metrics['avg_days_to_pay']:.2f} days."
        )
    if ap_metrics["avg_days_past_due"] is not None:
        summary_lines.append(
            f"- Average payment timing vs due date (closed AP): {ap_metrics['avg_days_past_due']:.2f} days (positive = late)."
        )
    summary_lines.append(
        f"- Late closed AP invoices: {ap_metrics['late_closed']} ({ap_metrics['late_rate']:.2f}%)."
    )
    summary_lines.append(
        f"- Closed AP invoices with non-zero stored amount_due: {ap_metrics['closed_with_nonzero_amount_due']}."
    )
    summary_lines.append(
        f"- AP exceptions/anomalies flagged: {len(anomalies_ap)}."
    )

    if top_ap:
        ap_top_text = "; ".join(
            f"{r['counterparty']} ({r['invoice_count']} inv, face={_money(r['total_face_value'])})"
            for r in top_ap
        )
        summary_lines.append(f"- Top AP creditors: {ap_top_text}.")
    else:
        summary_lines.append("- Top AP creditors: None.")

    summary_lines.append("")

    # --- COMBINED SECTION ---
    summary_lines.append("Combined (AR + AP)")
    summary_lines.append(
        f"- Closed invoices analysed: AR={ar_metrics['closed_count']}, AP={ap_metrics['closed_count']}, Total={total_closed}."
    )
    if avg_days_to_pay_all is not None:
        summary_lines.append(
            f"- Average days issue/funded -> paid (closed invoices): {avg_days_to_pay_all:.2f} days."
        )
    if avg_days_past_due_all is not None:
        summary_lines.append(
            f"- Average payment timing vs due date (closed invoices): {avg_days_past_due_all:.2f} days (positive = late)."
        )
    summary_lines.append(f"- Late closed invoices total: {late_closed_total}.")
    summary_lines.append(f"- Closed invoices with non-zero stored amount_due total: {closed_with_balance_total}.")
    summary_lines.append(f"- Total exceptions/anomalies flagged: {len(anomalies)}.")
    summary_lines.append(
        "- Use with bank transaction analysis to test whether invoice payment timing aligns with cash movements (AR inflows vs AP outflows)."
    )

    # IMPORTANT: keep line breaks so Sales Notes clearly shows AR and AP separately
    summary = "\n".join(summary_lines)

    # 8) Build HTML sections (CLEARLY SEPARATED AR / AP / COMBINED)

    # Optional note to reduce confusion around amount_due semantics
    amount_due_note_html = """
    <div style="margin:0 0 14px 0; padding:10px 12px; border:1px solid #e6e6e6; border-radius:6px; background:#fafafa; font-size:12px; color:#333;">
      <strong>Note:</strong> <code>amount_due</code> is shown as stored in the source rows. Depending on your schema/process, this may represent the invoice face/contractual due amount rather than remaining outstanding balance at close.
    </div>
    """

    # --- AR Overview ---
    ar_overview_rows = [
        {"metric": "AR API rows", "value": total_ar_api},
        {"metric": "AR Uploaded rows", "value": total_ar_uploaded},
        {"metric": "Closed AR invoices analysed", "value": ar_metrics["closed_count"]},
        {"metric": "Late closed AR invoices", "value": ar_metrics["late_closed"]},
        {"metric": "Late closed AR %", "value": f"{ar_metrics['late_rate']:.2f}%"},
        {"metric": "Closed AR invoices w/ non-zero stored amount_due", "value": ar_metrics["closed_with_nonzero_amount_due"]},
        {"metric": "Avg days issue/funded -> paid (AR)", "value": f"{ar_metrics['avg_days_to_pay']:.2f}" if ar_metrics["avg_days_to_pay"] is not None else ""},
        {"metric": "Avg days paid vs due (AR; + = late)", "value": f"{ar_metrics['avg_days_past_due']:.2f}" if ar_metrics["avg_days_past_due"] is not None else ""},
        {"metric": "AR anomalies flagged", "value": len(anomalies_ar)},
    ]
    ar_overview_html = _html_table("AR Overview (Accounts Receivable)", ar_overview_rows, [("metric", "Metric"), ("value", "Value")])

    # --- AP Overview ---
    ap_overview_rows = [
        {"metric": "AP Uploaded rows", "value": total_ap_uploaded},
        {"metric": "Closed AP invoices analysed", "value": ap_metrics["closed_count"]},
        {"metric": "Late closed AP invoices", "value": ap_metrics["late_closed"]},
        {"metric": "Late closed AP %", "value": f"{ap_metrics['late_rate']:.2f}%"},
        {"metric": "Closed AP invoices w/ non-zero stored amount_due", "value": ap_metrics["closed_with_nonzero_amount_due"]},
        {"metric": "Avg days issue/funded -> paid (AP)", "value": f"{ap_metrics['avg_days_to_pay']:.2f}" if ap_metrics["avg_days_to_pay"] is not None else ""},
        {"metric": "Avg days paid vs due (AP; + = late)", "value": f"{ap_metrics['avg_days_past_due']:.2f}" if ap_metrics["avg_days_past_due"] is not None else ""},
        {"metric": "AP anomalies flagged", "value": len(anomalies_ap)},
    ]
    ap_overview_html = _html_table("AP Overview (Accounts Payable)", ap_overview_rows, [("metric", "Metric"), ("value", "Value")])

    # --- Combined Overview ---
    combined_overview_rows = [
        {"metric": "Closed invoices analysed (AR+AP)", "value": total_closed},
        {"metric": "Late closed invoices total", "value": late_closed_total},
        {"metric": "Closed invoices w/ non-zero stored amount_due total", "value": closed_with_balance_total},
        {"metric": "Avg days issue/funded -> paid (AR+AP)", "value": f"{avg_days_to_pay_all:.2f}" if avg_days_to_pay_all is not None else ""},
        {"metric": "Avg days paid vs due (AR+AP; + = late)", "value": f"{avg_days_past_due_all:.2f}" if avg_days_past_due_all is not None else ""},
        {"metric": "Total anomalies flagged", "value": len(anomalies)},
    ]
    combined_overview_html = _html_table("Combined Overview (AR + AP)", combined_overview_rows, [("metric", "Metric"), ("value", "Value")])

    # --- Counterparty tables split ---
    party_ar_html = _html_table(
        "AR Counterparty Summary (Debtors only)",
        party_rows_ar[:DISPLAY_LIMIT_PARTY_ROWS],
        [
            ("counterparty", "Debtor"),
            ("invoice_count", "Invoices"),
            ("closed_count", "Closed"),
            ("open_count", "Open"),
            ("total_face_value", "Total Face Value"),
            ("total_amount_funded", "Total Amount Funded"),
            ("total_amount_due", "Total Amount Due"),
            ("closed_with_balance_count", "Closed w/ Balance"),
            ("late_payment_count", "Late Closed"),
            ("on_time_or_early_count", "On-time/Early Closed"),
            ("avg_days_to_pay", "Avg Days to Pay"),
            ("avg_days_past_due", "Avg Days vs Due"),
        ],
    )

    party_ap_html = _html_table(
        "AP Counterparty Summary (Creditors only)",
        party_rows_ap[:DISPLAY_LIMIT_PARTY_ROWS],
        [
            ("counterparty", "Creditor"),
            ("invoice_count", "Invoices"),
            ("closed_count", "Closed"),
            ("open_count", "Open"),
            ("total_face_value", "Total Face Value"),
            ("total_amount_funded", "Total Amount Funded"),
            ("total_amount_due", "Total Amount Due"),
            ("closed_with_balance_count", "Closed w/ Balance"),
            ("late_payment_count", "Late Closed"),
            ("on_time_or_early_count", "On-time/Early Closed"),
            ("avg_days_to_pay", "Avg Days to Pay"),
            ("avg_days_past_due", "Avg Days vs Due"),
        ],
    )

    # --- Transaction summaries split (still based on combined transaction buckets, but shown per side) ---
    txn_ar_html = _html_table(
        "AR Transaction History Summary (transactions with AR invoices)",
        txn_rows_ar[:DISPLAY_LIMIT_TXN_ROWS],
        [
            ("transaction_id", "Transaction ID"),
            ("ar_invoice_count", "AR Inv"),
            ("ar_closed_count", "AR Closed"),
            ("total_face_value_ar", "AR Face"),
            ("total_amount_due_ar", "AR Amt Due"),
            ("first_issue_date", "First Issue/Funded"),
            ("latest_due_date", "Latest Due"),
            ("latest_payment_date", "Latest Paid"),
            ("counterparty_count", "Counterparties"),
            ("counterparties_sample", "Counterparty Sample"),
        ],
    )

    txn_ap_html = _html_table(
        "AP Transaction History Summary (transactions with AP invoices)",
        txn_rows_ap[:DISPLAY_LIMIT_TXN_ROWS],
        [
            ("transaction_id", "Transaction ID"),
            ("ap_invoice_count", "AP Inv"),
            ("ap_closed_count", "AP Closed"),
            ("total_face_value_ap", "AP Face"),
            ("total_amount_due_ap", "AP Amt Due"),
            ("first_issue_date", "First Issue/Funded"),
            ("latest_due_date", "Latest Due"),
            ("latest_payment_date", "Latest Paid"),
            ("counterparty_count", "Counterparties"),
            ("counterparties_sample", "Counterparty Sample"),
        ],
    )

    # --- Timelines split ---
    timeline_ar_html = _html_table(
        "AR Closed Invoice Payment Timeline (Receivables)",
        timeline_rows_ar[:DISPLAY_LIMIT_TXN_ROWS],
        [
            ("transaction_id", "Transaction ID"),
            ("inv_number", "Invoice #"),
            ("counterparty", "Debtor"),
            ("invoice_state", "State"),
            ("issue_date", "Issue/Funded Date"),
            ("due_date", "Due Date"),
            ("date_paid", "Date Paid"),
            ("days_to_pay", "Days to Pay"),
            ("days_past_due", "Days vs Due"),
            ("face_value", "Face Value"),
            ("amount_funded", "Amount Funded"),
            ("amount_due_at_close", "Amount Due @ Close"),
            ("api_match", "AR API Match"),
            ("api_issue_date_delta_days", "API Issue Δ Days"),
            ("api_due_date_delta_days", "API Due Δ Days"),
            ("api_face_value_delta", "API Face Δ"),
            ("api_amount_funded_delta", "API Funded Δ"),
            ("api_amount_due_delta", "API AmtDue Δ"),
        ],
    )

    timeline_ap_html = _html_table(
        "AP Closed Invoice Payment Timeline (Payables)",
        timeline_rows_ap[:DISPLAY_LIMIT_TXN_ROWS],
        [
            ("transaction_id", "Transaction ID"),
            ("inv_number", "Invoice #"),
            ("counterparty", "Creditor"),
            ("invoice_state", "State"),
            ("issue_date", "Issue/Funded Date"),
            ("due_date", "Due Date"),
            ("date_paid", "Date Paid"),
            ("days_to_pay", "Days to Pay"),
            ("days_past_due", "Days vs Due"),
            ("face_value", "Face Value"),
            ("amount_funded", "Amount Funded"),
            ("amount_due_at_close", "Amount Due @ Close"),
        ],
    )

    # --- Anomalies split ---
    anomalies_ar_html = _html_table(
        "AR Exceptions / Anomalies (Closed receivable invoices)",
        anomalies_ar[:DISPLAY_LIMIT_ANOMALIES],
        [
            ("transaction_id", "Transaction ID"),
            ("inv_number", "Invoice #"),
            ("counterparty", "Debtor"),
            ("invoice_state", "State"),
            ("issue_date", "Issue/Funded"),
            ("due_date", "Due"),
            ("date_paid", "Paid"),
            ("days_to_pay", "Days to Pay"),
            ("days_past_due", "Days vs Due"),
            ("amount_due_at_close", "Amt Due @ Close"),
            ("reasons", "Reasons"),
        ],
    )

    anomalies_ap_html = _html_table(
        "AP Exceptions / Anomalies (Closed payable invoices)",
        anomalies_ap[:DISPLAY_LIMIT_ANOMALIES],
        [
            ("transaction_id", "Transaction ID"),
            ("inv_number", "Invoice #"),
            ("counterparty", "Creditor"),
            ("invoice_state", "State"),
            ("issue_date", "Issue/Funded"),
            ("due_date", "Due"),
            ("date_paid", "Paid"),
            ("days_to_pay", "Days to Pay"),
            ("days_past_due", "Days vs Due"),
            ("amount_due_at_close", "Amt Due @ Close"),
            ("reasons", "Reasons"),
        ],
    )

    # Section wrappers for visual separation
    ar_section_header = """
    <div style="margin:8px 0 12px 0; padding:8px 10px; background:#eef6ff; border:1px solid #d8eaff; border-radius:6px;">
      <h3 style="margin:0; font-size:14px;">AR (Accounts Receivable) Analysis</h3>
    </div>
    """

    ap_section_header = """
    <div style="margin:16px 0 12px 0; padding:8px 10px; background:#fff6ee; border:1px solid #ffe4cc; border-radius:6px;">
      <h3 style="margin:0; font-size:14px;">AP (Accounts Payable) Analysis</h3>
    </div>
    """

    combined_section_header = """
    <div style="margin:16px 0 12px 0; padding:8px 10px; background:#f5f5f5; border:1px solid #e5e5e5; border-radius:6px;">
      <h3 style="margin:0; font-size:14px;">Combined View (AR + AP)</h3>
    </div>
    """

    table_html = (
        amount_due_note_html
        + ar_section_header
        + ar_overview_html
        + party_ar_html
        + txn_ar_html
        + timeline_ar_html
        + anomalies_ar_html
        + ap_section_header
        + ap_overview_html
        + party_ap_html
        + txn_ap_html
        + timeline_ap_html
        + anomalies_ap_html
        + combined_section_header
        + combined_overview_html
    )

    return summary, table_html