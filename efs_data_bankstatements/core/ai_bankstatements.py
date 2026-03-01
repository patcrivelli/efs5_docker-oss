# efs_data_bankstatements/core/ai_bankstatements.py

import json
import logging
import re
from typing import Any, Dict, List
from django.views.decorators.csrf import csrf_exempt          # ✅ correct module
from django.views.decorators.http import require_GET, require_POST

from django.conf import settings
import google.generativeai as genai
# efs_data_bankstatements/core/views.py
import json
import logging
from datetime import datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path

from django.conf import settings
from django.db import transaction
from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.csrf import csrf_exempt          # ✅ correct module
from django.views.decorators.http import require_GET, require_POST

import re
import statistics
from django.db.models import Q




log = logging.getLogger(__name__)


def _get_api_key() -> str:
    key = getattr(settings, "GEMINI_API_KEY", "") or ""
    if not key:
        raise RuntimeError("Missing settings.GEMINI_API_KEY")
    return key


def _get_model() -> str:
    return getattr(settings, "GEMINI_MODEL", "gemini-2.5-flash")


def strip_code_fences(s: str) -> str:
    s = (s or "").strip()
    s = re.sub(r"^```[a-zA-Z0-9]*\s*", "", s)
    s = re.sub(r"\s*```$", "", s)
    return s.strip()


def _extract_text(resp) -> str:
    """
    Gemini SDK sometimes returns partial text in resp.text.
    This tries candidates/parts to reliably reconstruct the full output.
    """
    # Best case
    t = (getattr(resp, "text", "") or "").strip()
    if t:
        return t

    # Rebuild from candidates/parts
    out = []
    candidates = getattr(resp, "candidates", None) or []
    for c in candidates:
        content = getattr(c, "content", None)
        parts = getattr(content, "parts", None) or []
        for p in parts:
            piece = getattr(p, "text", None)
            if piece:
                out.append(piece)
    return "".join(out).strip()


def _compact_per_account(metrics: Dict[str, Any], cap: int = 8) -> List[Dict[str, Any]]:
    per = (metrics or {}).get("per_account", []) or []
    out = []
    for a in per[:cap]:
        out.append({
            "account_holder": a.get("account_holder"),
            "account_name": a.get("account_name"),
            "bank_name": a.get("bank_name"),
            "start_balance": a.get("start_balance"),
            "end_balance": a.get("end_balance"),
            "avg_daily_balance": a.get("avg_daily_balance"),
            "total_inflows": a.get("total_inflows"),
            "total_outflows": a.get("total_outflows"),
            "net_cashflow": a.get("net_cashflow"),
            "days_negative": a.get("days_negative"),
            "max_drawdown": a.get("max_drawdown"),
            "volatility": a.get("volatility"),
            "txn_count": a.get("txn_count"),
        })
    return out


def _compact_detailed_supplier_analysis(detailed: Dict[str, Any], top_n: int = 5) -> Dict[str, Any]:
    """
    Trim detailed transaction analysis payload so prompt size stays controlled.
    Expected shape (from views.py) includes top_suppliers with monthly totals + intervals.
    """
    if not detailed or not isinstance(detailed, dict):
        return {}

    suppliers = []
    for s in (detailed.get("top_suppliers") or [])[:top_n]:
        suppliers.append({
            "supplier": s.get("supplier"),
            "total_paid_6m": s.get("total_paid_6m"),
            "payment_count": s.get("payment_count"),
            "avg_payment": s.get("avg_payment"),
            "avg_days_between": s.get("avg_days_between"),
            "intervals": (s.get("intervals") or [])[:20],
            "interval_change_sequence": (s.get("interval_change_sequence") or [])[:20],
            "interval_trend": s.get("interval_trend"),
            "potential_cashflow_stress_signal": s.get("potential_cashflow_stress_signal"),
            "monthly_totals": (s.get("monthly_totals") or [])[:6],
        })

    return {
        "window_months": detailed.get("window_months"),
        "window_start": detailed.get("window_start"),
        "as_of": detailed.get("as_of"),
        "match_basis": detailed.get("match_basis"),
        "matched_abn": detailed.get("matched_abn"),
        "matched_acn": detailed.get("matched_acn"),
        "top_suppliers": suppliers,
    }


def generate_bankstatements_sales_memo(payload: dict) -> str:
    """
    Returns plain text memo for Sales Notes.
    Will auto-continue until all required headings exist and length looks complete.

    Supports:
    - Existing summary metrics/serviceability payload
    - Optional detailed transaction analysis payload (e.g. recurring supplier payments)
      under payload["detailed_transaction_analysis"] or payload["detailed_analysis"].
    """
    api_key = _get_api_key()
    model_name = _get_model()

    genai.configure(api_key=api_key)
    model = genai.GenerativeModel(model_name)

    required_headings = [
        "Summary",
        "Key positives",
        "Key concerns / red flags",
        "What we should ask / verify",
        "Recommendation",
    ]

    def has_all_headings(text: str) -> bool:
        t = (text or "").lower()
        return all(h.lower() in t for h in required_headings)

    def looks_truncated(text: str) -> bool:
        t = (text or "").strip()
        if not t:
            return True
        bad_end = t.endswith((" a", " an", " the", " for", " of", " to", " and", " but", " because", "-"))
        return (len(t) < 900) or bad_end or (not has_all_headings(t))

    # Compact the input so the model gets the useful parts, especially if detailed analysis is included.
    metrics = (payload or {}).get("metrics", {}) or {}
    serviceability = (payload or {}).get("serviceability", {}) or {}
    widget_state = (payload or {}).get("widget_state", {}) or {}
    detailed = (
        (payload or {}).get("detailed_transaction_analysis")
        or (payload or {}).get("detailed_analysis")
        or {}
    )

    compact_input = {
        "abn": (payload or {}).get("abn"),
        "widget_state": {
            "months": widget_state.get("months"),
            "amount_borrowed": widget_state.get("amount_borrowed"),
            "interest_rate_pct": widget_state.get("interest_rate_pct"),
            "selected_accounts": widget_state.get("selected_accounts", []),
            "detailed_analysis": widget_state.get("detailed_analysis", False),
        },
        "metrics": {
            "as_of": metrics.get("as_of"),
            "window_start": metrics.get("window_start"),
            "window_months": metrics.get("window_months"),
            "overall": (metrics.get("overall") or {}),
            "per_account": _compact_per_account(metrics),
        },
        "serviceability": serviceability,
    }

    if detailed:
        compact_input["detailed_transaction_analysis"] = _compact_detailed_supplier_analysis(detailed)

    instructions = [
        "Write a practical credit memo (MIN 250 words, MAX 500 words).",
        "Use ONLY the provided numbers and facts. Do not invent facts.",
        "Do NOT output JSON. Do NOT use markdown. Do NOT use code fences.",
        "Use headings exactly and include ALL headings: Summary, Key positives, Key concerns / red flags, What we should ask / verify, Recommendation.",
        "Recommendation must be Approve / Conditional / Decline with reasons and (if conditional) explicit conditions.",
        "Do not stop early. Complete all sections fully.",
        "Explain WHY negative net cashflow and days_negative matters for repayments.",
        "Identify which account(s) drive negative cashflow/drawdown using per_account fields.",
    ]

    if detailed:
        instructions.extend([
            "Detailed transaction analysis is included. Use it to comment on recurring supplier payment behaviour.",
            "Specifically reference the 5 largest supplier payments over the last 6 months (if present).",
            "Comment on monthly supplier payment trends and whether payment spacing (days between payments) is stretching, stable, or tightening.",
            "If payment intervals are getting longer, explain this may indicate cash flow stress (but do not overstate certainty).",
            "If no recurring supplier patterns are present, state that clearly.",
        ])

    prompt_obj = {
        "task": (
            "Write INTERNAL SALES NOTES for a lender based on bank statement metrics + serviceability"
            + (" + detailed transaction-level supplier payment analysis." if detailed else ".")
        ),
        "instructions": instructions,
        "input": compact_input,
    }

    base_prompt = json.dumps(prompt_obj, default=str)

    try:
        resp = model.generate_content(
            base_prompt,
            generation_config={"temperature": 0.2, "max_output_tokens": 3072},
        )
        memo = strip_code_fences(_extract_text(resp))
    except Exception as e:
        log.exception("Gemini memo generate_content failed")
        return f"AI generation failed: {e}"

    # Auto-continue up to N times until memo is complete
    max_continuations = 3
    i = 0
    while i < max_continuations and looks_truncated(memo):
        i += 1

        missing = [h for h in required_headings if h.lower() not in (memo or "").lower()]
        missing_str = ", ".join(missing) if missing else "None"

        continue_prompt = (
            "You stopped early. Continue EXACTLY from where you left off.\n"
            "Rules:\n"
            "- Plain text only.\n"
            "- Do NOT repeat text already written.\n"
            "- Ensure ALL headings exist and complete the missing ones.\n"
            f"- Missing headings: {missing_str}\n\n"
            "So far:\n"
            f"{memo}\n\n"
            "Continue:"
        )

        try:
            resp2 = model.generate_content(
                continue_prompt,
                generation_config={"temperature": 0.2, "max_output_tokens": 3072},
            )
            add = strip_code_fences(_extract_text(resp2))
            if add:
                memo = (memo.rstrip() + "\n" + add.lstrip()).strip()
            else:
                break
        except Exception:
            log.exception("Gemini memo continuation failed")
            break

    return (memo or "").strip()

# efs_data_bankstatements/core/ai_bankstatements.py

import json
import logging
import re
from typing import Any, Dict, List

from django.conf import settings
import google.generativeai as genai

log = logging.getLogger(__name__)


def _get_api_key() -> str:
    key = getattr(settings, "GEMINI_API_KEY", "") or ""
    if not key:
        raise RuntimeError("Missing settings.GEMINI_API_KEY")
    return key


def _get_model() -> str:
    return getattr(settings, "GEMINI_MODEL", "gemini-2.5-flash")


def strip_code_fences(s: str) -> str:
    s = (s or "").strip()
    s = re.sub(r"^```[a-zA-Z0-9]*\s*", "", s)
    s = re.sub(r"\s*```$", "", s)
    return s.strip()


def _extract_text(resp) -> str:
    """
    Gemini SDK sometimes returns partial text in resp.text.
    This tries candidates/parts to reliably reconstruct the full output.
    """
    t = (getattr(resp, "text", "") or "").strip()
    if t:
        return t

    out = []
    candidates = getattr(resp, "candidates", None) or []
    for c in candidates:
        content = getattr(c, "content", None)
        parts = getattr(content, "parts", None) or []
        for p in parts:
            piece = getattr(p, "text", None)
            if piece:
                out.append(piece)
    return "".join(out).strip()


def _compact_per_account(metrics: Dict[str, Any], cap: int = 8) -> List[Dict[str, Any]]:
    per = (metrics or {}).get("per_account", []) or []
    out = []
    for a in per[:cap]:
        out.append({
            "account_holder": a.get("account_holder"),
            "account_name": a.get("account_name"),
            "bank_name": a.get("bank_name"),
            "start_balance": a.get("start_balance"),
            "end_balance": a.get("end_balance"),
            "avg_daily_balance": a.get("avg_daily_balance"),
            "total_inflows": a.get("total_inflows"),
            "total_outflows": a.get("total_outflows"),
            "net_cashflow": a.get("net_cashflow"),
            "days_negative": a.get("days_negative"),
            "max_drawdown": a.get("max_drawdown"),
            "volatility": a.get("volatility"),
            "txn_count": a.get("txn_count"),
        })
    return out


def _compact_detailed_supplier_analysis(detailed: Dict[str, Any], top_n: int = 5) -> Dict[str, Any]:
    """
    Trim detailed transaction analysis payload so prompt size stays controlled.
    Expected shape (from views.py) includes top_suppliers with monthly totals + intervals.
    """
    if not detailed or not isinstance(detailed, dict):
        return {}

    suppliers = []
    for s in (detailed.get("top_suppliers") or [])[:top_n]:
        suppliers.append({
            "supplier": s.get("supplier"),
            "total_paid_6m": s.get("total_paid_6m"),
            "payment_count": s.get("payment_count"),
            "avg_payment": s.get("avg_payment"),
            "avg_days_between": s.get("avg_days_between"),
            "intervals": (s.get("intervals") or [])[:20],
            "interval_change_sequence": (s.get("interval_change_sequence") or [])[:20],
            "interval_trend": s.get("interval_trend"),
            "stress_signal": s.get("stress_signal"),
            "monthly_totals": (s.get("monthly_totals") or [])[:6],
            "sample_descriptions": (s.get("sample_descriptions") or [])[:3],
        })

    # Support either "matched_by" (your current helper output) OR older keys
    matched_by = detailed.get("matched_by") or {}
    return {
        "window_months": detailed.get("window_months"),
        "match_basis": matched_by.get("logic") or detailed.get("match_basis"),
        "matched_abn": matched_by.get("abn") or detailed.get("matched_abn"),
        "matched_acn": matched_by.get("acn") or detailed.get("matched_acn"),
        "summary": detailed.get("summary") or {},
        "top_suppliers": suppliers,
    }


def generate_bankstatements_sales_memo(payload: dict) -> str:
    """
    Returns plain text memo for Sales Notes.
    Will auto-continue until all required headings exist and length looks complete.

    Supports:
    - Existing summary metrics/serviceability payload
    - Optional detailed transaction analysis payload (e.g. recurring supplier payments)
      under payload["detailed_transaction_analysis"] or payload["detailed_analysis"].
    """
    api_key = _get_api_key()
    model_name = _get_model()

    genai.configure(api_key=api_key)
    model = genai.GenerativeModel(model_name)

    required_headings = [
        "Summary",
        "Key positives",
        "Key concerns / red flags",
        "What we should ask / verify",
        "Recommendation",
    ]

    def has_all_headings(text: str) -> bool:
        t = (text or "").lower()
        return all(h.lower() in t for h in required_headings)

    def looks_truncated(text: str) -> bool:
        t = (text or "").strip()
        if not t:
            return True
        bad_end = t.endswith((" a", " an", " the", " for", " of", " to", " and", " but", " because", "-"))
        return (len(t) < 900) or bad_end or (not has_all_headings(t))

    metrics = (payload or {}).get("metrics", {}) or {}
    serviceability = (payload or {}).get("serviceability", {}) or {}
    widget_state = (payload or {}).get("widget_state", {}) or {}
    detailed = (
        (payload or {}).get("detailed_transaction_analysis")
        or (payload or {}).get("detailed_analysis")
        or {}
    )

    compact_input = {
        "abn": (payload or {}).get("abn"),
        "widget_state": {
            "months": widget_state.get("months"),
            "amount_borrowed": widget_state.get("amount_borrowed"),
            "interest_rate_pct": widget_state.get("interest_rate_pct"),
            "selected_accounts": widget_state.get("selected_accounts", []),
            "detailed_analysis": widget_state.get("detailed_analysis", False),
        },
        "metrics": {
            "as_of": metrics.get("as_of"),
            "window_start": metrics.get("window_start"),
            "window_months": metrics.get("window_months"),
            "overall": (metrics.get("overall") or {}),
            "per_account": _compact_per_account(metrics),
        },
        "serviceability": serviceability,
    }

    if detailed:
        compact_input["detailed_transaction_analysis"] = _compact_detailed_supplier_analysis(detailed)

    instructions = [
        "Write a practical credit memo (MIN 250 words, MAX 500 words).",
        "Use ONLY the provided numbers and facts. Do not invent facts.",
        "Do NOT output JSON. Do NOT use markdown. Do NOT use code fences.",
        "Use headings exactly and include ALL headings: Summary, Key positives, Key concerns / red flags, What we should ask / verify, Recommendation.",
        "Recommendation must be Approve / Conditional / Decline with reasons and (if conditional) explicit conditions.",
        "Do not stop early. Complete all sections fully.",
        "Explain WHY negative net cashflow and days_negative matters for repayments.",
        "Identify which account(s) drive negative cashflow/drawdown using per_account fields.",
    ]

    if detailed:
        instructions.extend([
            "Detailed transaction analysis is included. You MUST use it in the memo.",
            "Specifically reference recurring supplier payments for the 5 largest suppliers by total paid over the last 6 months (if present).",
            "Comment on monthly supplier payment totals and whether payment spacing (days between payments) is stretching, stable, or tightening.",
            "If payment intervals are getting longer, explain that this may indicate cash flow stress (without overstating certainty).",
            "Include at least 2 explicit supplier names in Key concerns / red flags or Key positives when top_suppliers are present.",
            "If no recurring supplier patterns are present, state that clearly.",
        ])

    prompt_obj = {
        "task": (
            "Write INTERNAL SALES NOTES for a lender based on bank statement metrics + serviceability"
            + (" + detailed transaction-level supplier payment analysis." if detailed else ".")
        ),
        "instructions": instructions,
        "input": compact_input,
    }

    base_prompt = json.dumps(prompt_obj, default=str)

    try:
        resp = model.generate_content(
            base_prompt,
            generation_config={"temperature": 0.2, "max_output_tokens": 3072},
        )
        memo = strip_code_fences(_extract_text(resp))
    except Exception as e:
        log.exception("Gemini memo generate_content failed")
        return f"AI generation failed: {e}"

    max_continuations = 3
    i = 0
    while i < max_continuations and looks_truncated(memo):
        i += 1

        missing = [h for h in required_headings if h.lower() not in (memo or "").lower()]
        missing_str = ", ".join(missing) if missing else "None"

        continue_prompt = (
            "You stopped early. Continue EXACTLY from where you left off.\n"
            "Rules:\n"
            "- Plain text only.\n"
            "- Do NOT repeat text already written.\n"
            "- Ensure ALL headings exist and complete the missing ones.\n"
            f"- Missing headings: {missing_str}\n\n"
            "So far:\n"
            f"{memo}\n\n"
            "Continue:"
        )

        try:
            resp2 = model.generate_content(
                continue_prompt,
                generation_config={"temperature": 0.2, "max_output_tokens": 3072},
            )
            add = strip_code_fences(_extract_text(resp2))
            if add:
                memo = (memo.rstrip() + "\n" + add.lstrip()).strip()
            else:
                break
        except Exception:
            log.exception("Gemini memo continuation failed")
            break

    return (memo or "").strip()
