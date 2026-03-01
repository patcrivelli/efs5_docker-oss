# efs_data_financial/core/agent_code/assets.py
import logging
import html
from datetime import datetime
from decimal import Decimal

from django.apps import apps
from django.core.exceptions import ImproperlyConfigured

log = logging.getLogger(__name__)


def _get_model_by_name(name: str):
    """
    Resolve a model by class name across common app labels so this works
    whether models live in efs_data_financial, core, efs_data, etc.
    """
    for label in ("efs_data_financial", "efs_data_financial.core", "core", "efs_data"):
        try:
            m = apps.get_model(label, name)
            if m:
                return m
        except LookupError:
            pass

    for m in apps.get_models():
        if m.__name__ == name:
            return m

    labels = sorted({m._meta.app_label for m in apps.get_models()})
    raise ImproperlyConfigured(
        f"Could not resolve model {name}. Ensure it is in INSTALLED_APPS and migrated. "
        f"Known app labels: {labels}"
    )


def _to_dec(x) -> Decimal:
    if x is None or x == "":
        return Decimal("0")
    try:
        # Accept Decimal/float/str
        return Decimal(str(x).replace(",", "").replace("$", "").strip())
    except Exception:
        return Decimal("0")


def _fmt_money(d: Decimal) -> str:
    q = (d or Decimal("0")).quantize(Decimal("0.01"))
    return f"${q:,.2f}"


def run_analysis(abn=None, acn=None, transaction_id=None):
    """
    ASSETS analysis (Vehicles + Plant & Machinery).
    Returns (summary:str, table_html:str).
    Filters by ABN or ACN (prefers ABN), optionally narrows by transaction_id.
    """
    ident = abn or acn or ""
    ident_type = "ABN" if abn else ("ACN" if acn else "ID")
    log.info("[ASSETS] run_analysis start %s=%s tx=%s", ident_type, ident, transaction_id)
    print(f"[ASSETS] run_analysis: {ident_type}={ident} tx={transaction_id}")

    e = lambda s: html.escape(str(s or ""), quote=True)

    # -------- Models --------
    AssetScheduleRow = _get_model_by_name("AssetScheduleRow")  # Vehicles
    PPEAsset         = _get_model_by_name("PPEAsset")          # Plant & Machinery

    # -------- Querysets --------
    veh_qs = AssetScheduleRow.objects.all()
    ppe_qs = PPEAsset.objects.all()

    if abn:
        veh_qs = veh_qs.filter(abn=abn)
        ppe_qs = ppe_qs.filter(abn=abn)
    elif acn:
        veh_qs = veh_qs.filter(acn=acn)
        ppe_qs = ppe_qs.filter(acn=acn)

    if transaction_id:
        veh_qs = veh_qs.filter(transaction_id=transaction_id)
        ppe_qs = ppe_qs.filter(transaction_id=transaction_id)

    # -------- Totals (Vehicles) --------
    veh_count = veh_qs.count()
    total_fmv_v   = Decimal("0")
    total_fsv_v   = Decimal("0")
    total_olv_v   = Decimal("0")
    total_bv_v    = Decimal("0")
    total_lease_v = Decimal("0")
    total_nbv_v   = Decimal("0")

    for r in veh_qs.only("fmv_amount", "fsv_amount", "olv_amount", "bv_amount", "lease_os_amount", "nbv_amount"):
        total_fmv_v   += _to_dec(r.fmv_amount)
        total_fsv_v   += _to_dec(r.fsv_amount)
        total_olv_v   += _to_dec(r.olv_amount)
        total_bv_v    += _to_dec(r.bv_amount)
        total_lease_v += _to_dec(r.lease_os_amount)
        total_nbv_v   += _to_dec(r.nbv_amount)

    # -------- Totals (Plant & Machinery) --------
    ppe_count = ppe_qs.count()
    total_fmv_ppe   = Decimal("0")  # fair_market_value_ex_gst
    total_olv_ppe   = Decimal("0")  # orderly_liquidation_value_ex_gst
    total_bv_ppe    = Decimal("0")
    total_lease_ppe = Decimal("0")
    total_nbv_ppe   = Decimal("0")

    for r in ppe_qs.only(
        "fair_market_value_ex_gst",
        "orderly_liquidation_value_ex_gst",
        "bv_amount",
        "lease_os_amount",
        "nbv_amount",
    ):
        total_fmv_ppe   += _to_dec(r.fair_market_value_ex_gst)
        total_olv_ppe   += _to_dec(r.orderly_liquidation_value_ex_gst)
        total_bv_ppe    += _to_dec(r.bv_amount)
        total_lease_ppe += _to_dec(r.lease_os_amount)
        total_nbv_ppe   += _to_dec(r.nbv_amount)

    stamp = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")

    # -------- Summary (goes into Sales Notes for the Assets tab) --------
    lines = [
        f"[{stamp}] Assets analysis for ABN={e(abn) or 'N/A'}, ACN={e(acn) or 'N/A'}, TX={e(transaction_id) or 'N/A'}",
        "Vehicles (AssetScheduleRow):",
        f"- Items: {veh_count:,}",
        f"- FMV: {_fmt_money(total_fmv_v)}, FSV: {_fmt_money(total_fsv_v)}, OLV: {_fmt_money(total_olv_v)}",
        f"- BV: {_fmt_money(total_bv_v)}, Lease OS: {_fmt_money(total_lease_v)}, NBV: {_fmt_money(total_nbv_v)}",
        "Plant & Machinery (PPEAsset):",
        f"- Items: {ppe_count:,}",
        f"- FMV: {_fmt_money(total_fmv_ppe)}, OLV: {_fmt_money(total_olv_ppe)}",
        f"- BV: {_fmt_money(total_bv_ppe)}, Lease OS: {_fmt_money(total_lease_ppe)}, NBV: {_fmt_money(total_nbv_ppe)}",
    ]
    summary = "\n".join(lines)

    # No table rendering — keep API stable
    table_html = ""

    log.info("[ASSETS] run_analysis done veh=%d ppe=%d", veh_count, ppe_count)
    return summary, table_html
