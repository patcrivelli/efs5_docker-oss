
# ---- Agents page setup view code-----------------------------
# ---- Agents page setup view code-----------------------------
# ---- Agents page setup view code-----------------------------
# ---- Agents page setup view code-----------------------------



import logging
import requests
from django.conf import settings
from django.shortcuts import render, redirect

logger = logging.getLogger(__name__)

def _profile_base():
    return getattr(settings, "EFS_PROFILE_BASE_URL", "http://localhost:8002").rstrip("/")

def _api_key_header():
    return {"X-API-Key": getattr(settings, "INTERNAL_API_KEY", "dev-key")}

def fetch_originators():
    """Return a list of originators as dicts with keys id + originator."""
    try:
        r = requests.get(f"{_profile_base()}/api/originators/", timeout=5)
        r.raise_for_status()
        data = r.json()

        # If API already returns a list of dicts
        if isinstance(data, list):
            # make sure each entry is a dict
            return [o if isinstance(o, dict) else {"id": o, "originator": str(o)} for o in data]

        # If API returns {"originators": [...]}
        if isinstance(data, dict) and "originators" in data:
            return data["originators"]

        return []
    except Exception:
        logger.exception("Failed to fetch originators from efs_profile")
        return []


def base_context(request):
    originators = fetch_originators()
    selected = None
    selected_id = request.GET.get("originators")
    if selected_id:
        for o in originators:
            if str(o.get("id")) == str(selected_id):
                selected = o
                break
    return {"originators": originators, "selected_originator": selected}



# views.py
from .models import AgentSectionData, MemoryConfiguration

def agents_view(request):
    ctx = base_context(request)

    # build your available_models as you already do…
    services = {
        "efs_data_bureau": "http://localhost:8018/list-models/",
        "efs_data_financial": "http://localhost:8019/list-models/",
        "efs_data_bankstatements": "http://localhost:8020/list-models/",
    }
    all_models = []
    for service_name, url in services.items():
        try:
            resp = requests.get(url, timeout=5)
            if resp.status_code == 200:
                data = resp.json()
                for model in data.get("models", []):
                    all_models.append(f"{service_name}.{model}")
        except Exception as e:
            all_models.append(f"{service_name} (error: {e})")

    # IMPORTANT: provide the querysets the template expects
    ctx.update({
        "available_models": all_models,
        "agents": AgentSectionData.objects.all().order_by("-date_created"),
        "memory_configs": MemoryConfiguration.objects.filter(is_active=True).order_by("-created_at"),
    })

    # Render the file that actually exists: efs_agents/templates/agents.html
    return render(request, "agents.html", ctx)


# --- Form handler (sidebar Create Originator) ---
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

    # redirect back so dropdown refreshes
    return redirect("efs_agents:agents_home")

from django.shortcuts import render, redirect
from django.http import HttpResponse

# --- Agent stubs that match your HTML actions ---

from django.contrib import messages
from .models import AgentSectionData

from django.contrib import messages
from .models import AgentSectionData   # ✅ correct model

def save_agent(request):
    if request.method == "POST":
        business_function = request.POST.get("business_function")
        agent_name = request.POST.get("agent_name")
        persona = request.POST.get("create_persona")
        selected_models = request.POST.getlist("selected_models[]")

        try:
            AgentSectionData.objects.create(   # ✅ use correct model
                business_function=business_function,
                bot_name=agent_name,           # ✅ matches your model field
                persona=persona,
                selected_models=selected_models,
            )
            messages.success(request, f"Agent '{agent_name}' saved successfully.")
        except Exception as e:
            messages.error(request, f"Error saving agent: {e}")

    return redirect("efs_agents:agents_home")






import json
import logging
from django.contrib import messages
from django.http import HttpResponse
from django.shortcuts import redirect
from django.db import transaction

from .models import MemoryConfiguration, SemanticMemory, ProceduralMemory

logger = logging.getLogger(__name__)

def _safe_json(s: str):
    s = (s or "").strip()
    if not s:
        return None
    try:
        return json.loads(s)
    except Exception:
        return None

def save_memory_config(request):
    if request.method != "POST":
        return redirect("efs_agents:agents_home")

    try:
        attention_recent_inputs = "recent_inputs" in request.POST.getlist("attention_mechanisms")
        attention_recurring_topics = "recurring_topics" in request.POST.getlist("attention_mechanisms")
        attention_user_focus = "user_focus" in request.POST.getlist("attention_mechanisms")

        episodic_conversation_history = "history" in request.POST.getlist("episodic")
        episodic_user_preferences = "preferences" in request.POST.getlist("episodic")
        episodic_user_behavior = "behaviors" in request.POST.getlist("episodic")

        # ✅ LTM toggles from YOUR HTML names
        semantic_compliance_data = "compliance" in request.POST.getlist("semantic")
        procedural_strict_workflows = "strict" in request.POST.getlist("procedural")
        ltm_enable_rag = "enabled" in request.POST.getlist("rag")

        consolidation_vals = set(request.POST.getlist("consolidation"))
        consolidation_importance_based = "importance" in consolidation_vals
        consolidation_frequency_based = "frequency" in consolidation_vals
        consolidation_explicit_commands = "explicit" in consolidation_vals

        # slider + select names in your HTML are:
        # - relevance-threshold
        # - decay-period  (values: "7", "30", "never")
        try:
            ltm_relevance_threshold = float(request.POST.get("relevance-threshold", "0.7") or "0.7")
        except Exception:
            ltm_relevance_threshold = 0.7

        decay_raw = (request.POST.get("decay-period") or "7").strip()
        if decay_raw == "never":
            decay_period_days = 10_000  # or 0, or whatever “never” means to you
        else:
            try:
                decay_period_days = int(decay_raw)
            except Exception:
                decay_period_days = 7

        # ✅ Semantic entry from your HTML
        sem_category = (request.POST.get("semantic-category") or "").strip()
        sem_key      = (request.POST.get("semantic-key") or "").strip()
        sem_value    = (request.POST.get("semantic-value") or "").strip()
        sem_metadata = _safe_json(request.POST.get("semantic-metadata"))

        # ✅ Procedural entry from your HTML
        proc_rule_name = (request.POST.get("procedural-rule-name") or "").strip()
        proc_rule_type = (request.POST.get("procedural-rule-type") or "").strip()
        proc_condition = (request.POST.get("procedural-condition") or "").strip()
        proc_action    = (request.POST.get("procedural-action") or "").strip()
        proc_metadata  = _safe_json(request.POST.get("procedural-metadata"))

        # semantic/procedural enabled should be TRUE if any user filled fields or ticked checkbox
        semantic_enabled = bool(sem_category or sem_key or sem_value or semantic_compliance_data)
        procedural_enabled = bool(proc_rule_name or proc_rule_type or proc_condition or proc_action or procedural_strict_workflows)

        with transaction.atomic():
            cfg = MemoryConfiguration.objects.create(
                config_name=request.POST.get("config_name", "Default Memory Config"),
                description=request.POST.get("description", ""),

                # --- STM ---
                stm_max_tokens=request.POST.get("context-window-size", 8000),
                attention_recent_inputs=attention_recent_inputs,
                attention_recurring_topics=attention_recurring_topics,
                attention_user_focus=attention_user_focus,
                attention_custom_focus_rules=request.POST.get("attention-custom-rules", ""),

                token_management_strategy=request.POST.get("token-strategy", "preserve"),
                critical_keywords=request.POST.get("token-priority", ""),
                overflow_policy=request.POST.get("stm-overflow-policy", "discard_oldest"),

                episodic_conversation_history=episodic_conversation_history,
                episodic_user_preferences=episodic_user_preferences,
                episodic_user_behavior=episodic_user_behavior,
                episodic_retention_duration=request.POST.get("episodic-duration", "session"),

                # --- LTM ---
                framework=request.POST.get("framework") or "langchain",
                semantic_enabled=semantic_enabled,
                semantic_compliance_data=semantic_compliance_data,

                procedural_enabled=procedural_enabled,
                procedural_strict_workflows=procedural_strict_workflows,

                ltm_relevance_threshold=ltm_relevance_threshold,
                ltm_enable_rag=ltm_enable_rag,

                consolidation_importance_based=consolidation_importance_based,
                consolidation_frequency_based=consolidation_frequency_based,
                consolidation_explicit_commands=consolidation_explicit_commands,
                decay_period_days=decay_period_days,
            )

            sem_created = False
            if sem_category or sem_key or sem_value or isinstance(sem_metadata, dict):
                SemanticMemory.objects.create(
                    config=cfg,
                    agent=None,  # (optional) you can link an agent later
                    category=sem_category,
                    key=sem_key,
                    value=sem_value,
                    metadata=sem_metadata if isinstance(sem_metadata, dict) else None,
                )
                sem_created = True

            proc_created = False
            if proc_rule_name or proc_rule_type or proc_condition or proc_action or isinstance(proc_metadata, dict):
                ProceduralMemory.objects.create(
                    config=cfg,
                    agent=None,  # (optional) link later
                    rule_name=proc_rule_name,
                    rule_type=proc_rule_type,
                    condition_expression=proc_condition,
                    action=proc_action,
                    metadata=proc_metadata if isinstance(proc_metadata, dict) else None,
                )
                proc_created = True

        messages.success(
            request,
            f"✅ Memory config saved. Semantic row: {'Yes' if sem_created else 'No'} | "
            f"Procedural row: {'Yes' if proc_created else 'No'}"
        )

    except Exception as e:
        logger.exception("Failed to save memory config")
        messages.error(request, f"⚠️ Failed to save memory config: {e}")
        return HttpResponse(f"Error: {e}", status=500)

    return redirect("efs_agents:agents_home")


from django.views.decorators.csrf import csrf_protect
from django.shortcuts import redirect, get_object_or_404
from django.contrib import messages
from django.db.models import Q
from .models import (
    AgentSectionData,
    AgentTurnMemory,
    MemoryConfiguration,
    SemanticMemory,
    ProceduralMemory,
)



@csrf_protect
def assign_memory(request):
    if request.method == "POST":
        agent_id = request.POST.get("select_agent")
        memory_id = request.POST.get("memory_config_id")
        snippet = request.POST.get("memory_snippet", "")

        agent = get_object_or_404(AgentSectionData, id=agent_id)
        memory_config = get_object_or_404(MemoryConfiguration, id=memory_id)

        agent.memory_config = memory_config
        agent.memory_studio = {
            **(agent.memory_studio or {}),
            "snippet": snippet,
            "assigned_memory_config_name": memory_config.config_name,
            "assigned_memory_config_id": str(memory_config.id),
        }
        agent.save(update_fields=["memory_config", "memory_studio"])

        messages.success(request, f"Assigned '{memory_config.config_name}' to {agent.bot_name}")

    return redirect("efs_agents:agents_home")



#-----#-----#-----#-----#-----

#-----agent tabs 

#-----#-----#-----#-----#-----




# views.py
# views.py
from django.shortcuts import render
from .models import AgentSectionData, MemoryConfiguration

def agents_home(request):
    return render(request, "agents.html", {
        "agents": AgentSectionData.objects.all().order_by("-date_created"),
        "memory_configs": MemoryConfiguration.objects.filter(is_active=True).order_by("-created_at"),
        "selected_originator": None,
        "available_models": [],
        "originators": base_context(request).get("originators", []),
    })


def agent_archive(request):
    # TODO: return real archive data
    return HttpResponse("Agent archive placeholder.")


def memory_audit(request):
    # TODO: return real memory audit results
    return HttpResponse("Memory audit placeholder.")



""" 
from django.shortcuts import render
from django.views.decorators.http import require_GET
from .models import AgentSectionData   # ✅ import your model

@require_GET
def sales_agents_modal(request):

    saved_agents = AgentSectionData.objects.all().order_by("bot_name")

    ctx = {
        "abn": request.GET.get("abn", ""),
        "tx": request.GET.get("tx", ""),
        "saved_agents": saved_agents,   # ✅ pass agents to template
    }
    # File is templates/sales_agents.html (directly in templates)
    return render(request, "sales_agents.html", ctx)
"""







# efs_agents/core/views.py
import os, json, textwrap
import requests
from urllib.parse import quote
from django.conf import settings
from django.http import JsonResponse, HttpResponse, HttpResponseServerError
from django.shortcuts import render
from django.views.decorators.http import require_GET, require_POST
from .models import AgentSectionData

# ---- Settings helpers -------------------------------------------------

def _svc_base(setting_name: str, default_env: str = "", required: bool = True) -> str:
    # Prefer Django settings, then env var; consistently strip trailing slash
    val = (getattr(settings, setting_name, "") or os.getenv(setting_name, default_env) or "").rstrip("/")
    if required and not val:
        raise RuntimeError(f"Missing service base: {setting_name}")
    return val

DATA_SERVICE_BANKSTATEMENTS = lambda: _svc_base("DATA_SERVICE_BANKSTATEMENTS", "http://127.0.0.1:8020")
DATA_SERVICE_FINANCIAL      = lambda: _svc_base("DATA_SERVICE_FINANCIAL",      "http://127.0.0.1:8019", required=False)
DATA_SERVICE_BUREAU         = lambda: _svc_base("DATA_SERVICE_BUREAU",         "http://127.0.0.1:8018", required=False)

DEFAULT_TIMEOUT = int(os.getenv("DATA_SERVICE_TIMEOUT", getattr(settings, "DATA_SERVICE_TIMEOUT", "100")))


# ---- Modal (already correct: keep as-is) ------------------------------

@require_GET
def sales_agents_modal(request):
    saved_agents = AgentSectionData.objects.all().order_by("bot_name")
    ctx = {
        "abn": request.GET.get("abn", ""),
        "tx": request.GET.get("tx", ""),
        "saved_agents": saved_agents,
    }
    return render(request, "sales_agents.html", ctx)


# ---- Agent lookup (already OK) ---------------------------------------

@require_GET
def agent_by_name(request):
    bot_name = (request.GET.get("bot_name") or "").strip()
    if not bot_name:
        return JsonResponse({"ok": False, "error": "bot_name required"}, status=400)
    try:
        agent = AgentSectionData.objects.get(bot_name=bot_name)
    except AgentSectionData.DoesNotExist:
        return JsonResponse({"ok": False, "error": f"Agent '{bot_name}' not found"}, status=404)
    return JsonResponse({
        "ok": True,
        "agent": {
            "bot_name": agent.bot_name,
            "selected_models": agent.selected_models or [],
            "business_function": agent.business_function or "",
            "persona": agent.persona or "",
        }
    })




# ---- Start of Agents Modal code that interacts with in efs_sales & efs_data_financials-----------------------------
# ---- Start of Agents Modal code that interacts with in efs_sales & efs_data_financials-----------------------------
# ---- Start of Agents Modal code that interacts with in efs_sales & efs_data_financials-----------------------------
# ---- Start of Agents Modal code that interacts with in efs_sales & efs_data_financials-----------------------------



# ----# ----# ----# ----

# ---- fetch financial statement helpers   -----------------------------


# ----# ----# ----# ----# ----


# efs_agents/core/views.py
import json, logging, requests, re
from django.conf import settings
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt

logger = logging.getLogger(__name__)

FIN_SERVICE = getattr(settings, "DATA_SERVICE_FINANCIAL", "http://127.0.0.1:8019").rstrip("/")
TIMEOUT     = int(getattr(settings, "DATA_SERVICE_TIMEOUT", "100"))

def _digits_only(s):
    return "".join(ch for ch in str(s or "") if ch.isdigit())

def _fmt_money_any(v):
    if v in (None, "", "—"): return "—"
    t = str(v).strip().replace("$","").replace(",","")
    neg = t.startswith("(") and t.endswith(")")
    t = t.strip("()")
    try:
        n = float(t)
        if neg: n = -n
        return f"${n:,.2f}"
    except Exception:
        return str(v)

def _collect_year_headers(rows):
    headers = set()
    for r in rows or []:
        if isinstance(r, dict):
            for k in r.keys():
                if not k: continue
                s = str(k)
                if re.fullmatch(r"\d{4}", s):
                    headers.add(s)
                elif re.search(r"\d{2}", s):  # e.g. "Dec-24 ($000)"
                    headers.add(s)
    years = sorted([h for h in headers if re.fullmatch(r"\d{4}", h)], key=int)
    others = sorted([h for h in headers if h not in years])
    return years + others

def _detect_label_key(row):
    for k in ["Financial year", "Financial Year", "financial year",
              "\ufeffBalance Sheet Items ", "Balance Sheet Items",
              "\ufeffItem", "Item", "Account", "Label"]:
        if k in row:
            return k
    for k in row.keys():
        if not re.fullmatch(r"\d{4}", str(k)) and not re.search(r"\d{2}", str(k)):
            return k
    return None

def _rows_to_text_table(title, rows):
    if not isinstance(rows, list) or not rows:
        return [title, "(no data)"]
    headers = _collect_year_headers(rows)
    out = [title, "-" * len(title)]
    out.append(" | ".join(h.ljust(24) for h in (["Item"] + headers)))
    for r in rows:
        if not isinstance(r, dict): 
            continue
        lk = _detect_label_key(r)
        label = (str(r.get(lk, "")).strip() if lk else "").replace("\n"," ")
        if not label:
            continue
        line = [label.ljust(24)]
        for h in headers:
            line.append(_fmt_money_any(r.get(h)))
        out.append(" | ".join(s.rjust(24) for s in line))
    return out


def _fmt_money_any(v):
    if v in (None, "", "—"): return "—"
    t = str(v).strip().replace("$","").replace(",","")
    neg = t.startswith("(") and t.endswith(")")
    t = t.strip("()")
    try:
        n = float(t)
        if neg: n = -n
        return f"${n:,.2f}"
    except Exception:
        return str(v)

def _ledger_to_text_table(rows):
    """
    rows: [{"name": "...", "total_due": 123.0, "aged_current":..., "d0_30":..., "d31_60":..., "d61_90":..., "d90_plus":...}]
    Returns: list[str] lines to append to output.
    """
    out = ["Accounts Receivable Ledger", "---------------------------"]
    if not rows:
        out.append("(no AR ledger rows)")
        return out

    head = ["Debtor", "Aged Current", "0–30", "31–60", "61–90", "90+"]
    out.append(" | ".join(h.ljust(20) for h in head))

    tot_current = tot_0_30 = tot_31_60 = tot_61_90 = tot_90_plus = 0.0

    for r in rows or []:
        name = (r.get("name") or "—")[:40]
        current = r.get("aged_current")
        if current is None:
            current = r.get("total_due")
        n_current = float(current or 0.0)
        n_0_30   = float(r.get("d0_30")    or 0.0)
        n_31_60  = float(r.get("d31_60")   or 0.0)
        n_61_90  = float(r.get("d61_90")   or 0.0)
        n_90_plus= float(r.get("d90_plus") or 0.0)

        tot_current += n_current
        tot_0_30    += n_0_30
        tot_31_60   += n_31_60
        tot_61_90   += n_61_90
        tot_90_plus += n_90_plus

        line = [
            name.ljust(20),
            _fmt_money_any(n_current).rjust(20),
            (_fmt_money_any(n_0_30)    if n_0_30    else "—").rjust(20),
            (_fmt_money_any(n_31_60)   if n_31_60   else "—").rjust(20),
            (_fmt_money_any(n_61_90)   if n_61_90   else "—").rjust(20),
            (_fmt_money_any(n_90_plus) if n_90_plus else "—").rjust(20),
        ]
        out.append(" | ".join(line))

    out.append("")
    out.append(
        "Totals".ljust(20) + " | " +
        _fmt_money_any(tot_current).rjust(20) + " | " +
        (_fmt_money_any(tot_0_30)  if tot_0_30  else "—").rjust(20) + " | " +
        (_fmt_money_any(tot_31_60) if tot_31_60 else "—").rjust(20) + " | " +
        (_fmt_money_any(tot_61_90) if tot_61_90 else "—").rjust(20) + " | " +
        (_fmt_money_any(tot_90_plus) if tot_90_plus else "—").rjust(20)
    )
    return out

def _ledger_to_text_table_named(title, rows):
    tbl = _ledger_to_text_table(rows)
    if tbl:
        tbl[0] = title or "Ledger"
        if len(tbl) > 1:
            tbl[1] = "-" * len(tbl[0])
    return tbl


# ----  Net asset value helpers   -----------------------------

def _fmt_num(n):
    try:
        return f"{float(n):,.0f}"
    except Exception:
        return str(n)

def _fmt_pct1(v):
    try:
        return f"{float(v):.1f}"
    except Exception:
        return str(v)

def _render_snapshot_headers(snaps: list[dict]) -> list[str]:
    """
    snaps: nav_js['snapshots_all'] (newest→oldest), each:
      {id, created_at, abn, transaction_id, source_tab,
       advance_rate_pct, selected_total_amount, available_funds_amount}
    """
    out = ["Saved NAV Snapshots (matching tx/abn)", "----------------------------------"]
    if not snaps:
        out.append("(none)")
        return out

    # Show newest first, grouped implicitly by time; include tab label
    for s in snaps:
        created = s.get("created_at", "—")
        tab     = s.get("source_tab", "—")
        adv     = _fmt_pct1(s.get("advance_rate_pct"))
        sel     = _fmt_money_any(s.get("selected_total_amount"))
        avail   = _fmt_money_any(s.get("available_funds_amount"))
        out.append(f"- [{tab}] {created} | Advance Rate: {adv}% | Selected Total: {sel} | Available Funds: {avail}")
    return out


def _try_get_json_qs(base_url: str, params: dict | None = None, timeout: int = TIMEOUT):
    try:
        r = requests.get(base_url, params=params or {}, timeout=timeout)
    except requests.RequestException as e:
        return None, 502, f"Upstream error: {e}"
    if not r.ok:
        try:
            _ = r.json()
            return _, r.status_code, r.text
        except Exception:
            return None, r.status_code, (r.text or f"HTTP {r.status_code}")
    try:
        return r.json(), r.status_code, ""
    except ValueError:
        return None, 502, "Invalid JSON from upstream"


def _asset_lines_to_text_table_named(title: str, rows: list[dict]) -> list[str]:
    """
    Pretty table for NAVAssetLine / NAVPlantandequipmentLine rows.
    Dynamically includes BV, Lease Outstanding, NBV columns when present.
    rows items look like:
      {
        "make": "...", "model": "...", "type": "...",
        "year_of_manufacture": "...",
        "fsv_amount": number, "fmv_amount": number,
        "bv_amount": number|null,
        "lease_os_amount": number|null,
        "nbv_amount": number|null
      }
    """
    out = [title, "-" * len(title)]
    if not rows:
        out.append("(none)")
        return out

    # Detect which optional columns are present (any row with a non-null / non-empty value)
    has_bv   = any(r.get("bv_amount")        not in (None, "", "—") for r in rows)
    has_lease= any(r.get("lease_os_amount")  not in (None, "", "—") for r in rows)
    has_nbv  = any(r.get("nbv_amount")       not in (None, "", "—") for r in rows)

    head = ["Make", "Model", "Type", "Year", "FSV", "FMV"]
    if has_bv:    head.append("BV")
    if has_lease: head.append("Lease O/S")
    if has_nbv:   head.append("NBV")

    out.append(" | ".join(h.ljust(24) for h in head))

    for r in rows:
        mk = (r.get("make") or "")[:40]
        md = (r.get("model") or "")[:60]
        tp = (r.get("type") or "")[:40]
        yr = (r.get("year_of_manufacture") or "")

        line = [
            mk.ljust(24),
            md.ljust(24),
            tp.ljust(24),
            str(yr).ljust(8),
            _fmt_money_any(r.get("fsv_amount")).rjust(14),
            _fmt_money_any(r.get("fmv_amount")).rjust(14),
        ]

        if has_bv:
            line.append(_fmt_money_any(r.get("bv_amount")).rjust(14))
        if has_lease:
            line.append(_fmt_money_any(r.get("lease_os_amount")).rjust(14))
        if has_nbv:
            line.append(_fmt_money_any(r.get("nbv_amount")).rjust(14))

        out.append(" | ".join(line))

    return out





#---------------------

  #  bankstatements code helpers

#---------------------



import os
from urllib.parse import quote

BANK_SERVICE = getattr(settings, "DATA_SERVICE_BANKSTATEMENTS", None) or \
               os.getenv("EFS_DATA_BANKSTATEMENTS_URL", "http://127.0.0.1:8020")
BANK_SERVICE = BANK_SERVICE.rstrip("/")

def _bank_base() -> str:
    return BANK_SERVICE

def _fetch_bank_accounts_and_summary(abn_digits: str, months: int = 6, accounts: list[str] | None = None):
    """
    Calls efs_data_bankstatements for:
      - /display_bank_account_data/<abn>/
      - /bankstatements/summary/<abn>/?months=...
    Optional: accounts=['uuid','uuid'] to scope the summary.
    """
    base = _bank_base()
    url_accounts = f"{base}/display_bank_account_data/{quote(abn_digits)}/"
    url_summary  = f"{base}/bankstatements/summary/{quote(abn_digits)}/?months={int(months)}"
    if accounts:
        url_summary += f"&accounts={','.join(accounts)}"

    try:
        r1 = requests.get(url_accounts, timeout=TIMEOUT)
        r1.raise_for_status()
        acc_payload = r1.json()
        if not acc_payload or (isinstance(acc_payload, dict) and not acc_payload.get("success", True)):
            raise RuntimeError("accounts endpoint returned an error")

        r2 = requests.get(url_summary, timeout=TIMEOUT)
        r2.raise_for_status()
        summary_payload = r2.json()
    except requests.RequestException as e:
        raise RuntimeError(f"Upstream error: {e}") from e
    except ValueError:
        raise RuntimeError("Invalid JSON from bank service")

    accounts_data = (acc_payload.get("data") if isinstance(acc_payload, dict) else acc_payload) or []
    return accounts_data, (summary_payload or {})



def _bank_report_block(abn_digits: str, summary_js: dict) -> str:
    ov = summary_js.get("overall") or {}
    per = summary_js.get("per_account") or []
    lines = [
        "BANK STATEMENTS DATA",
        "--------------------",
        f"ABN: {abn_digits}",
        f"Window: {summary_js.get('window_start','—')} → {summary_js.get('as_of','—')} "
        f"({summary_js.get('window_months','?')} months)",
        "",
        "Overall",
        "-------",
        f"Accounts: {ov.get('num_accounts', 0)}",
        f"Start Balance: ${float(ov.get('start_balance',0.0)):,.2f}",
        f"End Balance:   ${float(ov.get('end_balance',0.0)):,.2f}",
        f"Avg Daily Bal: ${float(ov.get('avg_daily_balance',0.0)):,.2f}",
        f"Inflows:       ${float(ov.get('total_inflows',0.0)):,.2f}",
        f"Outflows:      ${float(ov.get('total_outflows',0.0)):,.2f}",
        f"Net Cashflow:  ${float(ov.get('net_cashflow',0.0)):,.2f}",
        f"Days Negative: {int(ov.get('days_negative',0))}",
        f"Max Drawdown:  ${float(ov.get('max_drawdown',0.0)):,.2f}",
        ""
    ]

    if per:
        lines += ["Top Accounts by Net Cashflow", "-------------------------------"]
        top = sorted(per, key=lambda p: abs(float(p.get("net_cashflow") or 0.0)), reverse=True)[:5]
        for p in top:
            lines.append(
                f"- {p.get('account_holder') or '—'} / {p.get('account_name') or '—'}: "
                f"net ${float(p.get('net_cashflow') or 0.0):,.2f}, "
                f"end ${float(p.get('end_balance') or 0.0):,.2f}, "
                f"days<0 {int(p.get('days_negative') or 0)}"
            )
    return "\n".join(lines).rstrip()



# ----  -----------------------------

#PPSR helpers 

# ----  -----------------------------


def _ppsr_service_base() -> str:
    return (getattr(settings, "DATA_SERVICE_FINANCIAL", None) or "http://127.0.0.1:8019").rstrip("/")


# --- PPSR helpers -------------------------------------------------------
from django.apps import apps
from django.conf import settings
import re
from uuid import UUID

PPSR_REQUIRED_FIELDS = {
    "transaction_id", "abn", "registration_number",
    "collateral_class_type", "collateral_type", "collateral_class_description",
    "are_proceeds_claimed", "proceeds_claimed_description",
    "is_security_interest_registration_kind", "are_assets_subject_to_control",
    "is_inventory", "is_pmsi", "is_subordinate",
    "giving_of_notice_identifier", "address_for_service",
}

def _get_registration_model():
    """Find the Registration model robustly (respects settings.PPSR_REGISTRATION_MODEL)."""
    override = getattr(settings, "PPSR_REGISTRATION_MODEL", None)
    if override and "." in override:
        app_label, model_name = override.split(".", 1)
        mdl = apps.get_model(app_label, model_name)
        if not mdl:
            raise LookupError(f"Could not resolve {override}")
        return mdl

    # common guesses first
    for guess in ("efs_data_financial", "efs_ppsr", "ppsr", "efs_data", "core"):
        try:
            mdl = apps.get_model(guess, "Registration")
            if mdl:
                names = {f.name for f in mdl._meta.get_fields()}
                if PPSR_REQUIRED_FIELDS.issubset(names):
                    return mdl
        except LookupError:
            pass

    # scan all apps
    for conf in apps.get_app_configs():
        try:
            mdl = conf.get_model("Registration")
        except LookupError:
            continue
        names = {f.name for f in mdl._meta.get_fields()}
        if PPSR_REQUIRED_FIELDS.issubset(names):
            return mdl

    raise LookupError(
        "Registration model not found. "
        "Set settings.PPSR_REGISTRATION_MODEL = 'app_label.Registration'."
)

def _extract_email_from_address(addr) -> str:
    """addr is typically a dict with {'lines': [...]}."""
    text = ""
    if isinstance(addr, dict):
        lines = addr.get("lines")
        if isinstance(lines, list):
            text = " ".join(str(x) for x in lines)
        else:
            text = str(lines or "")
    elif isinstance(addr, list):
        text = " ".join(str(x) for x in addr)
    else:
        text = str(addr or "")
    m = re.search(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", text)
    return m.group(0) if m else ""

def _ppsr_fetch_db_rows_for_response(tx: str | None, abn_digits: str | None):
    """Return list of dict rows with requested fields + extracted email."""
    try:
        Registration = _get_registration_model()
    except Exception:
        # don’t hard-fail the endpoint
        return []

    qs = None
    if tx:
        try:
            qs = Registration.objects.filter(transaction_id=UUID(tx))
        except Exception:
            qs = Registration.objects.filter(transaction_id=str(tx))

    if (qs is None or not qs.exists()) and abn_digits:
        qs = Registration.objects.filter(abn=abn_digits)

    if not qs:
        return []

    out = []
    for r in qs.iterator():
        out.append({
            "registration_number": r.registration_number,
            "collateral_class_type": r.collateral_class_type,
            "collateral_type": r.collateral_type,
            "collateral_class_description": r.collateral_class_description,
            "are_proceeds_claimed": r.are_proceeds_claimed,
            "proceeds_claimed_description": r.proceeds_claimed_description,
            "is_security_interest_registration_kind": r.is_security_interest_registration_kind,
            "are_assets_subject_to_control": r.are_assets_subject_to_control,
            "is_inventory": r.is_inventory,
            "is_pmsi": r.is_pmsi,
            "is_subordinate": r.is_subordinate,
            "giving_of_notice_identifier": r.giving_of_notice_identifier,
            "address_for_service_email": _extract_email_from_address(getattr(r, "address_for_service", None)),
        })
    return out




# -----------------------------------------



# ---- Bureau service base helpers 



# -----------------------------------------



BUREAU_SERVICE = getattr(settings, "DATA_SERVICE_BUREAU", "http://127.0.0.1:8018").rstrip("/")

def _safe_get(d, *keys, default=None):
    """Nested get: _safe_get(obj, 'report', 'anzsic', default={})"""
    cur = d
    for k in keys:
        try:
            cur = cur.get(k)
        except Exception:
            return default
        if cur is None:
            return default
    return cur if cur is not None else default

def _try_get_json(url: str, timeout: int = TIMEOUT):
    """GET url -> json or (None, http_status, text) on failure."""
    try:
        r = requests.get(url, timeout=timeout)
    except requests.RequestException as e:
        return None, 502, f"Upstream error: {e}"
    if not r.ok:
        # propagate non-2xx but don’t explode; caller decides how to handle
        try:
            _ = r.json()
            return _, r.status_code, r.text
        except Exception:
            return None, r.status_code, (r.text or f"HTTP {r.status_code}")
    try:
        return r.json(), r.status_code, ""
    except ValueError:
        return None, 502, "Invalid JSON from upstream"



def _bureau_report_block(abn_digits: str, score_js, hist_js, report_js) -> str:
    """
    Build a compact, human-readable block (no guessing).
    We keep it factual, with small counts/samples, while the full payload goes in 'data'.
    """
    lines = [
        "CREDIT BUREAU DATA",
        "-------------------",
        f"ABN: {abn_digits}",
        ""
    ]

    # Current score
    if isinstance(score_js, dict) and (score_js.get("current_credit_score") is not None):
        desc = score_js.get("description") or "—"
        item_code = score_js.get("item_code") or "—"
        lines += [
            "Current Credit Score",
            "--------------------",
            f"Score: {score_js.get('current_credit_score')}",
            f"Description: {desc}",
            f"Item Code: {item_code}",
            ""
        ]

    # Score history (limit for readability; UI gets full in data)
    if isinstance(hist_js, list) and hist_js:
        lines += ["Score History (latest)", "----------------------"]
        for h in hist_js[:12]:
            lines.append(f"- {h.get('date','—')}: {h.get('score','—')}")
        lines.append("")

    # Report top-level signals/counters if present
    # Your /bureau/summary returns:
    # {abn, acn, creditEnquiries, itemCode, description, report: { ...big... }, ...}
    # We’ll show a small “signals” line and a few samples.
    if isinstance(report_js, dict) and report_js:
        credit_enquiries = (
            report_js.get("creditEnquiries")
            or report_js.get("credit_enquiries")
            or _safe_get(report_js, "report", "creditEnquiries")
            or 0
        )
        core = report_js.get("report") or {}
        cj = core.get("courtJudgements") or []
        pd = core.get("paymentDefaults") or []
        ins = core.get("insolvencies") or []
        meq = core.get("mercantileEnquiries") or []
        ato = core.get("atoTaxDefault")

        lines += [
            "Signals",
            "-------",
            f"Credit enquiries: {int(credit_enquiries or 0)}",
            f"Court judgements: {len(cj)}",
            f"Payment defaults: {len(pd)}",
            f"Insolvencies: {len(ins)}",
            f"Mercantile enquiries: {len(meq)}",
            f"ATO tax default flag: {bool(ato) if ato is not None else False}",
            ""
        ]

        # Small, raw samples (not an LLM summary)
        def _sample_block(title, arr, keys):
            if not arr:
                return
            lines.append(title)
            lines.append("-" * len(title))
            for row in arr[:3]:
                parts = []
                for k in keys:
                    if k in row:
                        parts.append(f"{k}: {row.get(k)}")
                if parts:
                    lines.append("- " + " | ".join(parts))
            lines.append("")

        _sample_block("Court Judgements (sample)", cj, ("action", "actionDate", "judgementAmount", "plaintiff", "location"))
        _sample_block("Payment Defaults (sample)", pd, ("debtor", "amount", "defaultDate", "status"))
        _sample_block("Insolvencies (sample)", ins, ("type", "startDate", "status"))

    return "\n".join(lines).rstrip()



def _fetch_bureau_bundle(abn_digits: str) -> dict:
    """
    Hit efs_data_bureau for:
      - summary:  GET /bureau/summary/<abn>/
      - score:    GET /bureau/score/<abn>/            (optional)
      - history:  GET /bureau/score_history/<abn>/    (optional)
    Any missing endpoints are tolerated.
    """
    out = {"abn": abn_digits, "credit_score": None, "score_history": [], "credit_report": None, "warnings": []}

    # Summary (required)
    url_summary = f"{BUREAU_SERVICE}/bureau/summary/{abn_digits}/"
    js, code, msg = _try_get_json(url_summary)
    if js is None:
        # 404 becomes a clean “not found” error for callers
        raise RuntimeError(f"bureau summary fetch failed ({code}): {msg}")
    out["credit_report"] = js

    # Score (optional)
    url_score = f"{BUREAU_SERVICE}/bureau/score/{abn_digits}/"
    js, code, msg = _try_get_json(url_score)
    if js is not None:
        # Normalize a likely shape: {"abn": "...", "current_credit_score": ..., "description": ..., "item_code": ...}
        out["credit_score"] = js
    else:
        if code not in (404, 501):
            out["warnings"].append(f"score endpoint not available ({code}): {msg}")

    # History (optional)
    url_hist = f"{BUREAU_SERVICE}/bureau/score_history/{abn_digits}/"
    js, code, msg = _try_get_json(url_hist)
    if js is not None:
        # Expect a list like [{"date": "YYYY-MM-DD", "score": 123}, ...]
        if isinstance(js, list):
            out["score_history"] = js
        else:
            out["score_history"] = js.get("items") or []
    else:
        if code not in (404, 501):
            out["warnings"].append(f"score_history endpoint not available ({code}): {msg}")

    return out




        # ---- initial offer code ----------------------------------------------




# ===== ====================
    


# ===== Initial offer and terms & conditions helpers


# ===== =========================




# efs_agents/core/views.py  (add near the other imports/helpers)
import os
from urllib.parse import quote
from datetime import date

DEFAULT_TIMEOUT = int(os.getenv("REQUESTS_DEFAULT_TIMEOUT", "10"))

def APPLICATION_AGGREGATE_BASE():
    # env or Django settings (if you prefer), fallback to 8016
    from django.conf import settings
    return (
        getattr(settings, "APPLICATION_AGGREGATE_BASE", None)
        or os.getenv("APPLICATION_AGGREGATE_BASE", "http://127.0.0.1:8016")
    ).rstrip("/")

def _num(x):
    if x is None:
        return None
    s = str(x).strip()
    if not s:
        return None
    neg = s.startswith("(") and s.endswith(")")
    s = s.strip("()").replace(",", "")
    try:
        v = float(s)
        return -v if neg else v
    except Exception:
        return None

def _fmt_money0(v):
    try:
        return f"${float(v):,.0f}"
    except Exception:
        return str(v)

def _fmt_pct2(v):
    try:
        return f"{float(v):.2f}%"
    except Exception:
        return str(v)

def _render_initial_offer_letter_from_terms(terms: dict) -> str:
    g = lambda k, d="": terms.get(k, d)

    originator = g("originator") or "—"
    abn        = g("abn") or "—"

    facility_limit        = _fmt_money0(g("facility_limit", 10000))
    legal_fees            = _fmt_money0(g("legal_fees", 850))
    establishment_fee     = _fmt_money0(g("establishment_fee", 5000))
    advanced_rate         = _fmt_pct2(g("advanced_rate", 80))
    minimum_term          = str(g("minimum_term", 36))
    notice_period         = str(g("notice_period", 9))
    recourse_period       = str(g("recourse_period", 90))
    service_fee_amount    = _fmt_money0(g("service_fee_amount", 1000))
    service_fee_percent   = _fmt_pct2(g("service_fee_percent", 1.25))
    concentration_amount  = _fmt_money0(g("concentration_amount", 50000))
    concentration_percent = _fmt_pct2(g("concentration_percent", 50))
    base_rate             = _fmt_pct2(g("base_rate", 6.59))
    charge_rate           = _fmt_pct2(g("charge_rate", 1.41))
    discount_per_invoice  = _fmt_pct2(g("discount_per_invoice", 1))

    # portable day-month-year (strftime %-d is unixy; fallback below)
    try:
        today_str = date.today().strftime("%-d %B %Y")
    except Exception:
        today_str = date.today().strftime("%d %B %Y")

    body = f"""\
{today_str}

Director(s)
{originator}
ABN: {abn}

Dear Director(s),

Indicative Letter of Offer

Bayes Capital is pleased to present {originator} with this indicative offer for an
Invoice Finance Facility on the following terms.

Facility Description
Confidential debtor finance facility including funding, accounts receivable service and credit advice. The facility is undisclosed.

Funding Percentage
Initial payment of up to {advanced_rate} of approved debtors.

Funding Limit
The initial funding limit of the facility is {facility_limit}.

Retention Release
Released on a daily basis when your customer pays the invoice.

Service Fee (higher of)
{service_fee_amount} plus GST or {service_fee_percent} of invoices to nominated debtors for the month plus GST.

Discount Charge
Interest is calculated on a daily basis and charged monthly on funds you have drawn.
The Discount Charge is {charge_rate} above the Base Rate of {base_rate} p.a.

Term
The minimum term is {minimum_term} months and the agreement will continue thereafter.

Notice Period
A notice period of {notice_period} months applies after the term.

Concentration Limit (lower of)
{concentration_amount} or {concentration_percent} of the debtor's ledger outstanding at any one time. Each debtor must have creditworthiness.

Recourse Period
{recourse_period} days from the invoice date we fund an invoice.

Establishment Fee
{establishment_fee} plus GST.

Legal Documentation
Our legal fee for one entity is {legal_fees} plus GST. Additional costs may apply for more than one company, company name changes and/or trust documentation.

This is an indicative, non-binding offer subject to standard due diligence and final approval.

Kind regards,
Bayes Capital
"""
    return body.strip()



from datetime import date

def _render_trade_finance_offer_letter_from_terms(terms: dict) -> str:
    g = lambda k, d="": terms.get(k, d)

    originator = g("originator") or "—"
    abn        = g("abn") or "—"

    facility_limit    = _fmt_money0(g("facility_limit", 25000))
    legal_fees        = _fmt_money0(g("legal_fees", 1000))
    establishment_fee = _fmt_money0(g("establishment_fee", 6000))
    advanced_rate     = _fmt_pct2(g("advanced_rate", 75))
    interest_rate     = _fmt_pct2(g("interest_rate", 15))
    minimum_term      = str(g("minimum_term", 24))
    notice_period     = str(g("notice_period", 6))
    payment_term      = str(g("payment_term", 120))
    num_installments  = str(g("num_installments", 4))
    installment_period= str(g("installment_period", 30))
    service_fee_amount= _fmt_money0(g("service_fee_amount", 1200))
    service_fee_pct   = _fmt_pct2(g("service_fee_percent", 1.5))
    base_rate         = _fmt_pct2(g("base_rate", 7.0))
    charge_rate       = _fmt_pct2(g("charge_rate", 1.6))

    try:
        today_str = date.today().strftime("%-d %B %Y")
    except Exception:
        today_str = date.today().strftime("%d %B %Y")

    body = f"""\
{today_str}

Director(s)
{originator}
ABN: {abn}

Dear Director(s),

Indicative Letter of Offer

Bayes Capital is pleased to present {originator} with this indicative offer for a
Trade Finance Facility on the following terms.

Facility Summary
---------------
Facility Limit: {facility_limit}
Advance Rate: {advanced_rate}
Interest Rate: {interest_rate}

Term & Notice
-------------
Minimum Term: {minimum_term} months
Notice Period: {notice_period} months

Repayment Profile
-----------------
Payment Term: {payment_term} days
Installments: {num_installments}
Installment Period: {installment_period} days

Fees (higher of)
----------------
Service Fee: {service_fee_amount} + GST OR {service_fee_pct} of eligible transactions + GST
Establishment Fee: {establishment_fee} + GST
Legal Fees: {legal_fees} + GST

Discount / Funding Charge
-------------------------
Charge Rate: {charge_rate} above Base Rate of {base_rate} p.a.

This is an indicative, non-binding offer subject to standard due diligence and final approval.

Kind regards,
Bayes Capital
"""
    return body.strip()



def _render_scf_offer_letter_from_terms(terms: dict) -> str:
    g = lambda k, d="": terms.get(k, d)

    originator = g("originator") or "—"
    abn        = g("abn") or "—"

    scf_limit          = _fmt_money0(g("scf_limit", 100000))
    scf_setup_fee      = _fmt_money0(g("scf_setup_fee", 1000))
    scf_discount_rate  = _fmt_pct2(g("scf_discount_rate", 0.5))
    scf_payment_terms  = str(g("scf_payment_terms", 60))
    scf_min_invoice    = _fmt_money0(g("scf_min_invoice", 500))
    scf_rate_per_inv   = _fmt_pct2(g("scf_rate_per_invoice", 0.25))

    try:
        today_str = date.today().strftime("%-d %B %Y")
    except Exception:
        today_str = date.today().strftime("%d %B %Y")

    body = f"""\
{today_str}

Director(s)
{originator}
ABN: {abn}

Dear Director(s),

Indicative Letter of Offer

Bayes Capital is pleased to present {originator} with this indicative offer for a
Supply Chain Finance Facility on the following terms.

Facility Summary
---------------
Program Limit: {scf_limit}
Discount Rate: {scf_discount_rate}
Payment Terms: {scf_payment_terms} days
Minimum Invoice Size: {scf_min_invoice}

Fees
----
Setup Fee: {scf_setup_fee} + GST
Service Charge: {scf_rate_per_inv} per invoice

This is an indicative, non-binding offer subject to standard due diligence and final approval.

Kind regards,
Bayes Capital
"""
    return body.strip()









def _fetch_deal_conditions_by_tx(tx: str) -> list[dict]:
    if not tx:
        return []

    base = APPLICATION_AGGREGATE_BASE()

    # Helper to normalize the response shape
    def _extract(payload):
        if isinstance(payload, list):
            return payload
        if isinstance(payload, dict):
            return payload.get("results") or payload.get("deal_conditions") or payload.get("data") or []
        return []

    headers = {"Accept": "application/json"}
    # If your aggregate service uses an internal key, include it:
    internal_key = getattr(settings, "INTERNAL_API_KEY", None)
    if internal_key:
        headers["X-Internal-Key"] = internal_key  # adjust header name if your service expects X-API-Key

    # 1) Try GET with querystring (nice if supported)
    url_list = f"{base}/api/deal-conditions/"
    try:
        resp = requests.get(url_list, params={"transaction_id": tx}, timeout=DEFAULT_TIMEOUT, headers=headers)
        if resp.status_code == 200:
            return _extract(resp.json())

        # 405 means: endpoint exists but GET not allowed -> try POST
        if resp.status_code == 405:
            resp2 = requests.post(url_list, json={"transaction_id": tx}, timeout=DEFAULT_TIMEOUT, headers=headers)
            if resp2.status_code == 200:
                return _extract(resp2.json())

        # any 404 etc -> continue to fallbacks below
    except Exception:
        pass

    # 2) Try common “by tx” URL shapes (GET)
    candidate_urls = [
        f"{base}/api/deal-conditions/by-tx/{quote(tx)}/",
        f"{base}/api/deal-conditions/tx/{quote(tx)}/",
    ]
    for url in candidate_urls:
        try:
            resp = requests.get(url, timeout=DEFAULT_TIMEOUT, headers=headers)
            if resp.status_code == 200:
                return _extract(resp.json())
        except Exception:
            continue

    return []


import logging
import requests
from django.conf import settings

def _render_conditions_block(conditions: list[dict], tx: str) -> str:
    """
    Renders conditions grouped by PRE/POST.
    Expects fields like:
      condition_type, title, description, assigned_to, created_by, is_completed, date_created
    """
    if not conditions:
        return f"""\
DEAL CONDITIONS (Transaction: {tx})
No conditions found for this transaction.
""".strip()

    pre = [c for c in conditions if (c.get("condition_type") or "").lower() == "pre"]
    post = [c for c in conditions if (c.get("condition_type") or "").lower() == "post"]

    def fmt_one(c: dict) -> str:
        title = (c.get("title") or "").strip() or "Untitled"
        desc  = (c.get("description") or "").strip()
        assigned = (c.get("assigned_to") or "Unassigned").strip()
        created  = (c.get("created_by") or "—").strip()
        created_dt = (c.get("date_created") or "").strip()

        line = f"- {title} (Assigned: {assigned} | Created: {created}"
        if created_dt:
            line += f" | {created_dt}"
        line += ")"
        if desc:
            line += f"\n  • {desc}"
        return line


    parts = [f"DEAL CONDITIONS (Transaction: {tx})"]

    parts.append("\nPRE-Settlement")
    parts.extend(fmt_one(c) for c in pre) if pre else parts.append("- None")

    parts.append("\nPOST-Settlement")
    parts.extend(fmt_one(c) for c in post) if post else parts.append("- None")

    return "\n".join(parts).strip()



def _compose_summary_prompt(*, agent, ticket_label, kind, abn, tx, raw_report, data, memory) -> str:
    """
    Minimal prompt composer. Replace/extend as needed.
    """
    persona = (getattr(agent, "persona", "") or "").strip()
    bot_name = (getattr(agent, "bot_name", "") or "Agent").strip()

    # Keep data bounded so prompts don’t explode
    data_snip = ""
    try:
        if data is not None:
            data_snip = json.dumps(data, ensure_ascii=False)[:6000]
    except Exception:
        data_snip = ""

    return f"""
You are {bot_name}, an internal credit/risk analyst agent.

PERSONA:
{persona or "(none)"}

MEMORY (use as context; do not invent facts):
{memory or "(no memory)"}

TASK:
- Ticket: {ticket_label}
- Kind: {kind}
- ABN: {abn or "—"}
- Transaction ID: {tx or "—"}

RAW REPORT INPUT (facts source):
{raw_report}

STRUCTURED DATA (may be partial):
{data_snip}

INSTRUCTIONS:
- Produce a clear analysis for this task.
- Do NOT invent numbers or facts.
- Use the RAW REPORT as source of truth.
- If you are uncertain, say what is missing.

Return only the analysis text.
""".strip()


from typing import Any


# ===== Agent summarization glue (INSERT THIS WHOLE FUNCTION) =====
def _agent_append_summary_if_any(body: dict, report: str, data: Any, ticket_label: str, kind: str, abn: str, tx: str):
    agent_id = (body.get("agent_id") or "").strip()
    if not agent_id:
        return report, None

    # Call internal Python (fast) instead of HTTP:
    try:
        agent = AgentSectionData.objects.get(id=agent_id)
    except AgentSectionData.DoesNotExist:
        return report + "\n\n(⚠️ Selected agent not found — skipping summary.)", None

    memory = _gather_agent_memory(agent)
    prompt = _compose_summary_prompt(
        agent=agent,
        ticket_label=ticket_label or "Task",
        kind=kind or "general",
        abn=abn,
        tx=tx,
        raw_report=report,
        data=data,
        memory=memory,
    )
    try:
        summary = _llm_complete(prompt)
        block = f"=== {ticket_label} — Agent {agent.bot_name} Summary ===\n{summary}"
        return (report + "\n\n" + block).rstrip(), {"agent": agent.bot_name, "summary": summary}
    except Exception as e:
        return (report + f"\n\n(⚠️ Agent summary failed: {e})").rstrip(), None









# ===== ====================
    


# ===== data check list helpers


# ===== =========================
    

from django.conf import settings

# Safe default if you don't already have TIMEOUT defined in this module
TIMEOUT = getattr(settings, "DEFAULT_UPSTREAM_TIMEOUT", 20)

def _fmt_yes_no(v: bool) -> str:
    return "Yes" if bool(v) else "No"

def _build_data_checklist_report(tx: str, status: dict) -> str:
    lines = [f"Data Checklist for TX {tx}", ""]
    lines.append("Model | Has data? | Matches | Total")
    lines.append("----- | --------- | ------- | -----")
    order = [
        "FinancialData",
        "AssetScheduleRow",
        "PPEAsset",
        "FinancialStatementNotes",
        "UploadedLedgerData",
        "UploadAPLedgerData",
    ]
    models = status.get("models", {})
    for name in order:
        info = models.get(name, {})
        lines.append(
            f"{name} | {_fmt_yes_no(info.get('exists', False))} | "
            f"{info.get('match_count', 0)} | {info.get('total_count', 0)}"
        )
    return "\n".join(lines).strip()






# ===== ====================
  
# ===== deal workshop helpers


# ===== =========================






# efs_agents/core/views.py (near your other helpers)
from decimal import Decimal


AGG_BASE = (getattr(settings, "APPLICATION_AGGREGATE_BASE", None) or "http://127.0.0.1:8016").rstrip("/")
FIN_BASE = (getattr(settings, "DATA_SERVICE_FINANCIAL", None) or "http://127.0.0.1:8019").rstrip("/")


def _d(v, default="0"):
   try:
       if v is None or v == "":
           return Decimal(default)
       return Decimal(str(v))
   except Exception:
       return Decimal(default)


def _fetch_aggregate_for_tx(tx: str):
   url = f"{AGG_BASE}/api/aggregate/by-tx/{tx}/"
   js, code, msg = _try_get_json(url, timeout=TIMEOUT)
   if js is None:
       raise RuntimeError(f"aggregate fetch failed ({code}): {msg}")
   return js


def _fetch_ar_snapshot_for_tx(tx: str):
   url = f"{FIN_BASE}/api/nav/ar/latest/{tx}/"
   js, code, msg = _try_get_json(url, timeout=TIMEOUT)
   if js is None:
       raise RuntimeError(f"AR snapshot fetch failed ({code}): {msg}")
   return js


def _fetch_rejected_face_sum_for_tx(tx: str):
   url = f"{FIN_BASE}/api/invoices/rejected-face-sum/{tx}/"
   js, code, msg = _try_get_json(url, timeout=TIMEOUT)
   if js is None:
       raise RuntimeError(f"Rejected invoices sum fetch failed ({code}): {msg}")
   return js


def _fetch_financial_full_for_tx(tx: str, abn_digits: str | None = None) -> dict:
    """
    Fetch the same payload used by kind == 'financial' so we can reuse fs_notes
    in other kinds (eg deal_workshop) without importing models.
    """
    if not tx:
        return {}

    base = f"{FIN_SERVICE}/financial/full_tx/{tx}/"
    url = f"{base}?abn={abn_digits}" if abn_digits else base

    try:
        r = requests.get(url, timeout=TIMEOUT)

        # Same fallback logic you already use in kind == "financial"
        if abn_digits and r.status_code == 400:
            try:
                err_js = r.json()
                err_text = (err_js.get("error") or "").lower()
            except Exception:
                err_text = (r.text or "").lower()

            if "financialdata has no 'transaction_id' column" in err_text or "pass ?abn=<11 digits>" in err_text:
                url_fallback = f"{FIN_SERVICE}/financial/full/{abn_digits}/"
                r = requests.get(url_fallback, timeout=TIMEOUT)

        if not r.ok:
            return {}

        return r.json() if r.content else {}

    except Exception:
        return {}


# efs_agents/core/views.py (near other helpers)

def _fmt_links_block(links, link_description: str):
    """
    links: list of dicts like:
      {"id":"22222222222","type":"abn", "state":"sales_review", "transaction_id":"..."}
    """
    lines = []
    lines.append("Linked entities (from Application Aggregate)")
    lines.append("------------------------------------------")

    if not links and not (link_description or "").strip():
        lines.append("(none)")
        return lines

    # Print links in a readable way
    if links:
        for i, l in enumerate(links, start=1):
            if not isinstance(l, dict):
                lines.append(f"{i}. {str(l)}")
                continue

            _id = (l.get("id") or "").strip()
            _type = (l.get("type") or "").strip().lower()
            _state = (l.get("state") or "").strip()
            _tx = (l.get("transaction_id") or "").strip()

            extra = []
            if _state:
                extra.append(f"state={_state}")
            if _tx:
                extra.append(f"tx={_tx}")

            suffix = f" [{', '.join(extra)}]" if extra else ""
            lines.append(f"{i}. {_id} ({_type.upper() if _type else 'ID'}){suffix}")
    else:
        lines.append("(links empty)")

    # Print link_description verbatim
    desc = (link_description or "").strip()
    if desc:
        lines.append("")
        lines.append("Link description (history)")
        lines.append("--------------------------")
        lines.append(desc)

    return lines


# efs_agents/core/views.py (near other helpers)

BANK_STATEMENT_NOTE_TYPES = {
    "bank statements",
    "bank statements detailed",
}

def _is_bank_statement_note_type(v: str) -> bool:
    return (v or "").strip().lower() in BANK_STATEMENT_NOTE_TYPES

def _filter_bank_statement_notes(fs_notes):
    """
    fs_notes is expected to be a list of dicts like:
      {
        "financial_data_type": "...",
        "notes": "...",
        "created_at": "...",
        "updated_at": "...",
        ...
      }
    """
    out = []
    for n in (fs_notes or []):
        if not isinstance(n, dict):
            continue
        ftype = n.get("financial_data_type") or ""
        if _is_bank_statement_note_type(ftype):
            out.append(n)
    return out


def _append_notes_block(lines, title, notes_list):
    """
    Appends a readable notes block to `lines` (list[str]).
    """
    lines.append("")
    lines.append(title)
    lines.append("-" * len(title))

    if not notes_list:
        lines.append("(none)")
        return

    for n in notes_list:
        k = (n.get("financial_data_type") or "General").strip()
        when = (n.get("updated_at") or n.get("created_at") or "")[:19]
        body = (n.get("notes") or "").rstrip()

        lines.append(f"- [{when}] {k}:")
        lines.append(body if body else "(empty)")
        lines.append("")





# ---- # ---- # ---- # ---- # ---- # ---- # ----
# ---- Memory helpers for the run_agent_analysis view in next section -----
# ---- # ---- # ---- # ---- # ---- # ---- # ----

import json
import logging
import os
import uuid
from typing import Optional

import requests
from django.conf import settings
from django.db import transaction
from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from .models import AgentSectionData, AgentTurnMemory

logger = logging.getLogger(__name__)

STM_LIMIT = int(getattr(settings, "AGENTS_STM_LIMIT", 5))
LTM_LIMIT = int(getattr(settings, "AGENTS_LTM_LIMIT", 200))  # optional cap
DEFAULT_TIMEOUT = int(os.getenv("DATA_SERVICE_TIMEOUT", getattr(settings, "DATA_SERVICE_TIMEOUT", "30")))

# Optional cosine distance for pgvector similarity search
try:
    from pgvector.django import CosineDistance
except Exception:
    try:
        from pgvector.django.functions import CosineDistance
    except Exception:
        CosineDistance = None


def _digits_only(s: str) -> str:
    return "".join(ch for ch in str(s or "") if ch.isdigit())


def _boolish(v) -> bool:
    if isinstance(v, bool):
        return v
    if v is None:
        return False
    if isinstance(v, (int, float)):
        return v != 0
    s = str(v).strip().lower()
    return s in ("1", "true", "yes", "y", "on")


# -----------------------
# Gemini LLM + Embeddings
# -----------------------

def _get_gemini_model():
    import google.generativeai as genai
    api_key = getattr(settings, "GEMINI_API_KEY", None)
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY is not set")
    genai.configure(api_key=api_key)
    model_name = getattr(settings, "GEMINI_MODEL_NAME", "gemini-2.0-flash")
    return genai.GenerativeModel(model_name)


def _llm_complete(prompt: str, *, temperature=0.2, max_tokens=1200):
    try:
        model = _get_gemini_model()
        resp = model.generate_content(prompt, generation_config={
            "temperature": temperature,
            "max_output_tokens": max_tokens,
        })
        return (resp.text or "").strip(), None
    except Exception as e:
        return "", f"exception:{e}"


import logging
from typing import Optional

from django.conf import settings

logger = logging.getLogger(__name__)


def _vector_dim_from_model() -> Optional[int]:
    """
    Reads VectorField dimension from AgentTurnMemory at runtime.
    Works whether you use `output_embedding` or `embedding`.
    """
    from .models import AgentTurnMemory  # local import avoids circulars

    # Prefer the actual VectorField dimensions
    for fname in ("output_embedding", "embedding"):
        try:
            f = AgentTurnMemory._meta.get_field(fname)
            dim = getattr(f, "dimensions", None)
            if dim:
                return int(dim)
        except Exception:
            continue

    # Fallback to settings
    dim = getattr(settings, "AGENTS_EMBED_DIM", None)
    try:
        return int(dim) if dim else None
    except Exception:
        return None


def _embed_text(text: str) -> Optional[list[float]]:
    text = (text or "").strip()
    if not text:
        return None

    api_key = getattr(settings, "GEMINI_API_KEY", None)
    if not api_key:
        logger.warning("Embedding skipped: GEMINI_API_KEY is not set in efs_agents settings.")
        return None

    embed_model = getattr(settings, "GEMINI_EMBED_MODEL", None)
    if not embed_model:
        logger.warning("Embedding skipped: GEMINI_EMBED_MODEL is not set in settings.")
        return None

    target_dim = _vector_dim_from_model()
    if not target_dim:
        logger.warning("Embedding skipped: could not determine VectorField dimensions.")
        return None

    text = text[:8000]

    try:
        import google.generativeai as genai
        genai.configure(api_key=api_key)

        if not hasattr(genai, "embed_content"):
            logger.warning("Embedding skipped: genai.embed_content not available in this SDK.")
            return None

        # ✅ Gemini embeddings model (v1beta embedContent)
        # Docs: gemini-embedding-001 :contentReference[oaicite:1]{index=1}
        model_name = str(embed_model).strip()
        if model_name.startswith("models/"):
            model_name = model_name
        else:
            model_name = "models/" + model_name

        # Different SDK versions use different arg names for dimensionality
        try:
            emb = genai.embed_content(
                model=model_name,
                content=text,
                task_type="retrieval_document",
                output_dimensionality=target_dim,
            )
        except TypeError:
            emb = genai.embed_content(
                model=model_name,
                content=text,
                task_type="retrieval_document",
                outputDimensionality=target_dim,
            )

        vec = emb.get("embedding") if isinstance(emb, dict) else None
        if not (isinstance(vec, list) and vec and isinstance(vec[0], (int, float))):
            logger.warning("Embedding failed: unexpected response shape: %s", type(emb))
            return None

        if len(vec) != target_dim:
            logger.warning("Embedding dim mismatch: got=%s expected=%s", len(vec), target_dim)
            return None

        return vec

    except Exception as e:
        logger.warning("Embedding failed: %s", e)
        return None


# -----------------------
# STM -> LTM compression
# -----------------------

def _compress_turn(kind: str, ticket_label: str, input_text: str, output_text: str) -> str:
    """
    LTM compression. Uses Gemini if available; otherwise falls back to truncation.
    """
    use_llm = bool(getattr(settings, "AGENTS_COMPRESS_WITH_LLM", True))
    src = (output_text or input_text or "").strip()
    if not src:
        return ""

    if not use_llm or not getattr(settings, "GEMINI_API_KEY", None):
        return src[:1200]

    prompt = f"""
Compress this agent interaction for long-term memory.

Return bullet points only:
- preserve key facts & numbers exactly
- preserve key risks/issues
- preserve decisions/recommendations
- preserve follow-ups

Constraints:
- Max 1200 characters
- No fluff

KIND: {kind}
LABEL: {ticket_label}

INPUT:
{(input_text or "").strip()}

OUTPUT:
{(output_text or "").strip()}
""".strip()

    out, err = _llm_complete(prompt, temperature=0.1, max_tokens=600)
    if err:
        return src[:1200]
    return (out or "").strip()[:1200]


# -----------------------
# Save + Promote STM->LTM
# -----------------------


# ===== ====================
    

# ===== AGENT code that works with task tile helpers  

# ===== =========================




@csrf_exempt
def run_agent_analysis(request):
    """
    RUN BUTTON endpoint (data collection + deterministic formatting only).
    ✅ NO LLM
    ✅ NO memory read/write
    ✅ Ignores agent_id intentionally
    Returns: { ok: true, report: "<printable block>", data: <raw payload> }
    """

    # ---- CORS preflight ----
    if request.method == "OPTIONS":
        resp = JsonResponse({"ok": True})
        resp["Access-Control-Allow-Origin"] = "*"
        resp["Access-Control-Allow-Methods"] = "POST, OPTIONS"
        resp["Access-Control-Allow-Headers"] = "Content-Type"
        return resp

    if request.method != "POST":
        return JsonResponse({"ok": False, "error": "Method not allowed"}, status=405)

    # ---- Parse body ----
    try:
        body = json.loads(request.body.decode("utf-8") or "{}")
    except Exception:
        return JsonResponse({"ok": False, "error": "Invalid JSON"}, status=400)

    def _clean(s):
        return "".join(ch for ch in str(s or "") if ch.isascii())

    kind = (body.get("kind") or "").strip().lower()
    tx   = _clean(body.get("transaction_id"))
    abn  = _clean(body.get("abn"))
    abn_digits = _digits_only(abn)

    # NOTE: ignore agent_id here on purpose (Run button is “data collection only”)
    # agent_id = (body.get("agent_id") or "").strip()

    # =====================================================================
    # FINANCIALS
    # =====================================================================
    if kind == "financial":
        # Choose upstream endpoint (prefer TX)
        if tx:
            base = f"{FIN_SERVICE}/financial/full_tx/{tx}/"
            url  = f"{base}?abn={abn_digits}" if abn_digits else base
            who  = f"Transaction ID: {tx}"
        elif abn_digits:
            url  = f"{FIN_SERVICE}/financial/full/{abn_digits}/"
            who  = f"ABN: {abn_digits}"
        else:
            return JsonResponse({"ok": False, "error": "transaction_id or abn required"}, status=400)

        # Fetch from data service
        try:
            r = requests.get(url, timeout=TIMEOUT)

            # Retry on ABN endpoint if TX not supported upstream
            if tx and abn_digits and r.status_code == 400:
                try:
                    err_js = r.json()
                    err_text = (err_js.get("error") or "").lower()
                except Exception:
                    err_text = (r.text or "").lower()

                if "financialdata has no 'transaction_id' column" in err_text or "pass ?abn=<11 digits>" in err_text:
                    url_fallback = f"{FIN_SERVICE}/financial/full/{abn_digits}/"
                    r = requests.get(url_fallback, timeout=TIMEOUT)

            if not r.ok:
                return JsonResponse({"ok": False, "error": (r.text or f"HTTP {r.status_code}").strip()}, status=r.status_code)

            js = r.json()
        except requests.RequestException as e:
            return JsonResponse({"ok": False, "error": f"Upstream error: {e}"}, status=502)
        except ValueError:
            return JsonResponse({"ok": False, "error": "Invalid JSON from data service"}, status=502)

        # Compose printable report (deterministic)
        company = (js.get("company") or js.get("company_name") or "—").strip()
        lines = [
            "FINANCIAL STATEMENTS DATA",
            "-------------------------",
            who,
            f"Company: {company}",
            ""
        ]

        # User-entered Financial Statement Notes
        user_notes = js.get("fs_notes") or []
        if user_notes:
            lines += ["Financial Statement Notes (User)", "------------------------------"]
            for n in user_notes:
                k = (n.get("financial_data_type") or "General").strip()
                when = (n.get("updated_at") or n.get("created_at") or "")[:19]
                note_body = (n.get("notes") or "").rstrip()
                lines.append(f"- [{when}] {k}:")
                lines.append(note_body if note_body else "(empty)")
                lines.append("")

        items = js.get("items") or []
        if not items:
            lines.append("(no financial rows)")
        else:
            for it in items:
                year = it.get("year") or "—"
                lines += [f"=== Year {year} ===", ""]
                lines += _rows_to_text_table("Profit & Loss", it.get("profit_loss"))
                lines.append("")
                lines += _rows_to_text_table("Balance Sheet", it.get("balance_sheet"))
                lines.append("")
                cf = it.get("cash_flow")
                if isinstance(cf, list) and cf:
                    lines += _rows_to_text_table("Cash Flow", cf)
                    lines.append("")
                notes = (it.get("financial_statement_notes") or "").strip()
                if notes:
                    lines += ["Notes to Financial Statements", "-" * 31, notes, ""]
                subs = it.get("subsidiaries") or []
                if subs:
                    lines += ["Subsidiaries", "-" * 12]
                    for s in subs:
                        lines.append(f"- {json.dumps(s, ensure_ascii=False)}")
                    lines.append("")

        lines.append("")
        lines += _ledger_to_text_table_named("Accounts Receivable Ledger", js.get("ar_ledger") or [])

        ap = js.get("ap_ledger") or []
        if ap:
            lines.append("")
            lines += _ledger_to_text_table_named("Accounts Payable Ledger", ap)

        debtors = js.get("debtors_list") or []
        if debtors:
            lines.append("")
            lines += ["Debtors", "-------"]
            for d in debtors:
                lines.append(f"- {d}")

        invs = js.get("invoices") or []
        if invs:
            lines.append("")
            lines += ["Invoices", "--------"]
            for inv in invs[:50]:
                lines.append(
                    f"- {inv.get('debtor','—')} | {inv.get('invoice_number','—')} | "
                    f"{_fmt_money_any(inv.get('amount_due'))} | due {inv.get('repayment_date','—')}"
                )

        raw_report = "\n".join(lines).rstrip()
        return JsonResponse({"ok": True, "report": raw_report, "data": js}, status=200)

    # =====================================================================
    # BUREAU (ABN required)
    # =====================================================================
    elif kind == "bureau":
        if not abn_digits or len(abn_digits) != 11:
            return JsonResponse({"ok": False, "error": "Valid 11-digit ABN required for bureau"}, status=400)

        try:
            bundle = _fetch_bureau_bundle(abn_digits)
        except RuntimeError as e:
            return JsonResponse({"ok": False, "error": str(e)}, status=502)

        raw_report = _bureau_report_block(
            abn_digits=abn_digits,
            score_js=bundle.get("credit_score"),
            hist_js=bundle.get("score_history"),
            report_js=bundle.get("credit_report"),
        )

        js = {
            "ok": True,
            "abn": abn_digits,
            "score": bundle.get("credit_score"),
            "score_history": bundle.get("score_history"),
            "credit_report": bundle.get("credit_report"),
            "warnings": bundle.get("warnings") or [],
        }

        return JsonResponse({"ok": True, "report": raw_report, "data": js}, status=200)

    # =====================================================================
    # PPSR (TX-first)
    # =====================================================================
    elif kind == "ppsr":
        base = _ppsr_service_base()
        if tx:
            url = f"{base}/ppsr/full_tx/{tx}/"
            if abn_digits:
                url += f"?abn={abn_digits}"
            who = f"Transaction ID: {tx}"
        elif abn_digits:
            url = f"{base}/ppsr/{abn_digits}/"
            who = f"ABN: {abn_digits}"
        else:
            return JsonResponse({"ok": False, "error": "transaction_id or abn required for PPSR"}, status=400)

        try:
            r = requests.get(url, timeout=TIMEOUT)
            if not r.ok:
                return JsonResponse({"ok": False, "error": (r.text or f"HTTP {r.status_code}").strip()}, status=r.status_code)
            js = r.json()
        except requests.RequestException as e:
            return JsonResponse({"ok": False, "error": f"PPSR upstream error: {e}"}, status=502)
        except ValueError:
            return JsonResponse({"ok": False, "error": "Invalid PPSR JSON from data service"}, status=502)

        db_rows = _ppsr_fetch_db_rows_for_response(tx=tx, abn_digits=abn_digits)

        counts = js.get("counts") or {}
        lines = [
            "PPSR DATA",
            "---------",
            who,
            f"Total: {counts.get('total', 0)} | Active: {counts.get('active', 0)} | Expired: {counts.get('expired', 0)}",
            f"PMSI: {counts.get('pmsi', 0)} | Subordinate: {counts.get('subordinate', 0)}",
            "",
            "Collateral breakdown:",
        ]
        for row in (js.get("collateral_breakdown") or []):
            lines.append(f"- {row.get('collateral_class_type','Unknown')}: {row.get('count',0)}")

        lines += ["", "Registrations:"]
        headers = [
            "registration_number",
            "collateral_class_type",
            "collateral_type",
            "collateral_class_description",
            "proceeds_claimed_description",
            "is_inventory",
            "is_pmsi",
            "address_for_service_email",
        ]
        lines.append(" | ".join(headers))
        lines.append(" | ".join(["---"] * len(headers)))

        def as_yes_no(v):
            return "Yes" if bool(v) else "No"

        if db_rows:
            for d in db_rows:
                row = [
                    d.get("registration_number") or "—",
                    d.get("collateral_class_type") or "—",
                    d.get("collateral_type") or "—",
                    d.get("collateral_class_description") or "—",
                    d.get("proceeds_claimed_description") or "—",
                    as_yes_no(d.get("is_inventory")),
                    as_yes_no(d.get("is_pmsi")),
                    d.get("address_for_service_email") or "—",
                ]
                lines.append(" | ".join(row))
        else:
            regs = js.get("registrations") or []
            for rrow in regs:
                email = _extract_email_from_address(rrow.get("address_for_service"))
                row = [
                    rrow.get("registration_number") or "—",
                    rrow.get("collateral_class_type") or "—",
                    rrow.get("collateral_type") or "—",
                    rrow.get("collateral_class_description") or "—",
                    rrow.get("proceeds_claimed_description") or "—",
                    as_yes_no(rrow.get("is_inventory")),
                    as_yes_no(rrow.get("is_pmsi")),
                    email or "—",
                ]
                lines.append(" | ".join(row))

        raw_report = "\n".join(lines).rstrip()
        ppsr_payload = {"ppsr_api": js, "registrations_detailed": db_rows}
        return JsonResponse({"ok": True, "report": raw_report, "data": ppsr_payload}, status=200)

    # =====================================================================
    # NET ASSET VALUE
    # =====================================================================
    elif kind == "net_asset_value":
        if not (tx or abn_digits):
            return JsonResponse({"ok": False, "error": "transaction_id or abn required for NAV"}, status=400)

        base = (getattr(settings, "DATA_SERVICE_FINANCIAL", None) or "http://127.0.0.1:8019").rstrip("/")

        assets_params = {}
        if abn_digits:
            assets_params["abn"] = abn_digits
        if tx:
            assets_params["tx"] = tx
        assets_js, assets_code, assets_msg = _try_get_json_qs(
            f"{base}/api/assets/summary/",
            params=assets_params,
            timeout=TIMEOUT
        )

        nav_params = {}
        if abn_digits:
            nav_params["abn"] = abn_digits
        if tx:
            nav_params["tx"] = tx
        nav_js, nav_code, nav_msg = _try_get_json_qs(
            f"{base}/api/nav/latest/",
            params=nav_params,
            timeout=TIMEOUT
        )

        lines = [
            "NET ASSET VALUE",
            "---------------",
            f"ABN: {abn_digits or '—'}",
            f"Transaction ID: {tx or '—'}",
            ""
        ]

        if isinstance(nav_js, dict) and nav_js.get("snapshot"):
            snapshots_all = nav_js.get("snapshots_all") or []
            lines += _render_snapshot_headers(snapshots_all)
            lines.append("")

            aset = nav_js.get("asset_lines") or []
            lines += _asset_lines_to_text_table_named("NAVAssetLine (Nominated Assets)", aset)
            lines.append("")

            pe = nav_js.get("plant_equipment_lines") or []
            lines += _asset_lines_to_text_table_named("NAVPlantandequipmentLine (Nominated Plant & Equipment)", pe)
            lines.append("")

            ar = nav_js.get("ar_lines") or []
            lines += _ledger_to_text_table_named(
                "NAVARLine (Nominated Accounts Receivable)",
                [
                    {
                        "name": r.get("debtor_name") or "—",
                        "aged_current": r.get("aged_current"),
                        "d0_30": r.get("d0_30"),
                        "d31_60": r.get("d31_60"),
                        "d61_90": r.get("d61_90"),
                        "d90_plus": r.get("d90_plus"),
                    }
                    for r in (ar or [])
                ],
            )
        else:
            if nav_code not in (404, 501):
                lines.append(f"⚠️ NAV snapshot unavailable ({nav_code}): {nav_msg}\n")

        raw_report = "\n".join(lines).rstrip()
        nav_payload = {"assets_summary": assets_js, "nav_latest": nav_js}
        return JsonResponse({"ok": True, "report": raw_report, "data": nav_payload}, status=200)

    # =====================================================================
    # BANK STATEMENTS
    # =====================================================================
    elif kind == "bank":
        if not abn_digits or len(abn_digits) != 11:
            return JsonResponse({"ok": False, "error": "Valid 11-digit ABN required for bank statements"}, status=400)

        include_bank_statements_data = _boolish(
            body.get("include_bank_statements_data")
            or body.get("include_bank_statements")
            or body.get("bank_statements_data")
        )

        try:
            months = int(body.get("months", 6))
        except Exception:
            months = 6

        accounts_filter = body.get("accounts")
        if isinstance(accounts_filter, str):
            accounts_filter = [x.strip() for x in accounts_filter.split(",") if x.strip()]

        try:
            accounts, summary = _fetch_bank_accounts_and_summary(
                abn_digits,
                months=months,
                accounts=accounts_filter if accounts_filter else None
            )
        except Exception as e:
            return JsonResponse({"ok": False, "error": str(e)}, status=502)

        printable = _bank_report_block(abn_digits, summary)

        # Optional bank statement notes block (still deterministic — no LLM)
        bank_statement_notes = []
        bank_notes_payload = {
            "included": include_bank_statements_data,
            "notes": [],
            "note_types_filter": ["Bank Statements", "Bank Statements Detailed"],
        }

        notes_block_text = ""
        if include_bank_statements_data:
            if not tx:
                notes_lines = [
                    "",
                    "Bank Statements Data (User Notes)",
                    "---------------------------------",
                    "⚠️ Toggle is ON but no transaction_id was provided, so bank statement notes could not be fetched."
                ]
                notes_block_text = "\n".join(notes_lines).rstrip()
            else:
                try:
                    fin_full = _fetch_financial_full_for_tx(tx, abn_digits=abn_digits)
                    fs_notes = fin_full.get("fs_notes") or []
                    bank_statement_notes = _filter_bank_statement_notes(fs_notes)

                    bank_notes_payload = {
                        "included": True,
                        "notes": bank_statement_notes,
                        "note_types_filter": ["Bank Statements", "Bank Statements Detailed"],
                    }

                    notes_lines = []
                    _append_notes_block(
                        notes_lines,
                        "Bank Statements Data (User Notes)",
                        bank_statement_notes
                    )
                    notes_block_text = "\n".join(notes_lines).rstrip()
                except Exception as e:
                    notes_lines = [
                        "",
                        "Bank Statements Data (User Notes)",
                        "---------------------------------",
                        f"⚠️ Unable to fetch bank statement notes from data service: {e}"
                    ]
                    notes_block_text = "\n".join(notes_lines).rstrip()

        report_parts = [printable]
        if notes_block_text:
            report_parts.append(notes_block_text)
        raw_report = "\n\n".join(part for part in report_parts if (part or "").strip()).strip()

        bank_payload = {
            "accounts": accounts,
            "summary": summary,
            "bank_statements_data": bank_notes_payload,
        }

        return JsonResponse({"ok": True, "report": raw_report, "data": bank_payload}, status=200)

    # =====================================================================
    # INITIAL OFFER
    # =====================================================================
    elif kind == "initial_offer":
        base = APPLICATION_AGGREGATE_BASE()

        if not tx:
            return JsonResponse({"ok": False, "error": "transaction_id (tx) required for initial_offer"}, status=400)

        # 1) Find the application by tx
        try:
            ctx_url = f"{base}/api/applications/{tx}/"
            r = requests.get(ctx_url, timeout=DEFAULT_TIMEOUT, headers={"Accept": "application/json"})
            r.raise_for_status()
            payload = r.json() or {}
        except Exception as e:
            return JsonResponse({"ok": False, "error": f"Upstream error: {e}"}, status=502)

        app = payload.get("application") or {}
        if not app:
            return JsonResponse({"ok": False, "error": f"No application found for tx={tx}"}, status=404)

        app_abn = _digits_only(app.get("abn") or "")
        app_acn = _digits_only(app.get("acn") or "")
        if not (app_abn or app_acn):
            return JsonResponse({"ok": False, "error": "Application has no ABN/ACN to fetch terms"}, status=400)

        raw_product = (app.get("product") or "").strip().lower()
        if "trade" in raw_product:
            app_product = "trade_finance"
        elif "invoice" in raw_product:
            app_product = "invoice_finance"
        elif "scf" in raw_product or "early" in raw_product or "supply" in raw_product:
            app_product = "supply_chain_finance"
        elif "insurance" in raw_product or "ipf" in raw_product:
            app_product = "ipf"
        else:
            app_product = "invoice_finance"

        requested_product = (body.get("product") or "").strip().lower()
        if requested_product in ("tf", "trade"):
            requested_product = "trade_finance"
        if requested_product in ("scf", "supply_chain"):
            requested_product = "supply_chain_finance"
        if requested_product in ("invoice", "if"):
            requested_product = "invoice_finance"
        if not requested_product:
            requested_product = app_product or "invoice_finance"

        # 2) Fetch terms by ABN/ACN
        terms_url = f"{base}/application/terms/fetch/"
        params = {}
        if app_abn:
            params["abn"] = app_abn
        if app_acn:
            params["acn"] = app_acn

        try:
            r = requests.get(terms_url, params=params, timeout=DEFAULT_TIMEOUT, headers={"Accept": "application/json"})
            r.raise_for_status()
            terms_payload = r.json() or {}
        except Exception as e:
            return JsonResponse({"ok": False, "error": f"Terms fetch upstream error: {e}"}, status=502)

        if not terms_payload.get("ok"):
            return JsonResponse({"ok": False, "error": "Terms fetch failed", "raw": terms_payload}, status=502)

        latest_map = terms_payload.get("latest") or {}
        latest_any = terms_payload.get("latest_any")
        latest = latest_map.get(requested_product) or latest_any

        if not latest:
            raw_report = "No terms found for this ABN/ACN."
            return JsonResponse({"ok": True, "report": raw_report, "data": terms_payload}, status=200)

        product = (latest.get("product") or requested_product or "invoice_finance").lower()

        if product == "trade_finance":
            offer_letter = _render_trade_finance_offer_letter_from_terms(latest)
        elif product == "supply_chain_finance":
            offer_letter = _render_scf_offer_letter_from_terms(latest)
        else:
            offer_letter = _render_initial_offer_letter_from_terms(latest)

        # 3) Deal conditions by tx
        conditions = []
        try:
            conditions = _fetch_deal_conditions_by_tx(tx)
            conditions_block = _render_conditions_block(conditions, tx)
        except Exception as e:
            conditions_block = f"DEAL CONDITIONS (Transaction: {tx})\n⚠️ Failed to fetch conditions: {e}"

        raw_report = f"{offer_letter}\n\n---\n\n{conditions_block}".rstrip()

        payload_out = {
            "transaction_id": tx,
            "application_product": app_product,
            "requested_product": requested_product,
            "application_abn": app_abn or None,
            "application_acn": app_acn or None,
            "terms_payload": terms_payload,
            "selected_terms": latest,
            "product": product,
            "conditions": conditions,
            "conditions_count": len(conditions),
        }

        return JsonResponse({"ok": True, "report": raw_report, "data": payload_out}, status=200)

    # =====================================================================
    # DATA CHECKLIST
    # =====================================================================
    elif kind == "data_checklist":
        if not tx:
            return JsonResponse({"ok": False, "error": "transaction_id is required for data_checklist"}, status=400)

        fin_base = (getattr(settings, "DATA_SERVICE_FINANCIAL", None) or "http://127.0.0.1:8019").rstrip("/")
        url = f"{fin_base}/api/data-checklist-status/"

        try:
            r = requests.post(url, json={"transaction_id": tx, "abn": abn_digits}, timeout=TIMEOUT)
            if not r.ok:
                try:
                    err = r.json()
                    err_text = err.get("error") or r.text or f"HTTP {r.status_code}"
                except Exception:
                    err_text = r.text or f"HTTP {r.status_code}"
                return JsonResponse({"ok": False, "error": err_text}, status=r.status_code)
            status_js = r.json()
        except requests.RequestException as e:
            return JsonResponse({"ok": False, "error": f"Upstream error: {e}"}, status=502)
        except ValueError:
            return JsonResponse({"ok": False, "error": "Invalid JSON from data service"}, status=502)

        raw_report = _build_data_checklist_report(tx, status_js)
        return JsonResponse({"ok": True, "report": raw_report, "data": status_js}, status=200)

    # =====================================================================
    # DEAL WORKSHOP
    # =====================================================================
    elif kind == "deal_workshop":
        if not tx:
            return JsonResponse({"ok": False, "error": "transaction_id required for deal_workshop"}, status=400)

        include_linked = _boolish(body.get("include_linked_entities"))

        # 1) Aggregate
        try:
            agg_js = _fetch_aggregate_for_tx(tx)
        except Exception as e:
            return JsonResponse({"ok": False, "error": f"Aggregate fetch error: {e}"}, status=502)

        if not agg_js.get("found"):
            raw_report = (
                "DEAL WORKSHOP\n"
                "-------------\n"
                f"Transaction ID: {tx}\n\n"
                "No Aggregate_applicationdata found for this transaction."
            )
            return JsonResponse({"ok": True, "report": raw_report, "data": {"aggregate": agg_js}}, status=200)

        company_name = agg_js.get("company_name") or agg_js.get("company") or "—"
        amount_requested = _d(agg_js.get("amount_requested"), "0")
        links = agg_js.get("links") or []
        link_description = agg_js.get("link_description") or ""

        # 2) AR snapshot
        try:
            ar_js = _fetch_ar_snapshot_for_tx(tx)
        except Exception as e:
            return JsonResponse({"ok": False, "error": f"AR snapshot error: {e}"}, status=502)

        if not ar_js.get("found"):
            raw_report = (
                "DEAL WORKSHOP\n"
                "-------------\n"
                f"Transaction ID: {tx}\n"
                f"Company: {company_name}\n\n"
                "No AR NetAssetValueSnapshot found for this transaction."
            )
            return JsonResponse({"ok": True, "report": raw_report, "data": {"aggregate": agg_js, "ar_snapshot": ar_js}}, status=200)

        adv_pct = _d(ar_js.get("advance_rate_pct"), "0")
        selected_total = _d(ar_js.get("selected_total_amount"), "0")
        available_old = _d(ar_js.get("available_funds_amount"), "0")

        # 3) rejected invoices summary
        try:
            rej_js = _fetch_rejected_face_sum_for_tx(tx)
        except Exception as e:
            return JsonResponse({"ok": False, "error": f"Rejected invoices error: {e}"}, status=502)

        rejected_total = _d(rej_js.get("rejected_face_value_total"), "0")
        rejected_count = int(rej_js.get("rejected_count") or 0)
        rejected_debtors = rej_js.get("rejected_debtors") or []
        rejected_debtors_count = int(rej_js.get("rejected_debtors_count") or len(rejected_debtors))

        adjusted_selected = selected_total - rejected_total
        if adjusted_selected < 0:
            adjusted_selected = Decimal("0")

        eligible_collateral = (adjusted_selected * adv_pct) / Decimal("100") if adv_pct else Decimal("0")
        cmp_symbol = "<=" if amount_requested <= eligible_collateral else ">"
        conclusion = (
            f"Amount requested {cmp_symbol} eligible collateral\n"
            f"Amount requested: {_fmt_money_any(amount_requested)}\n"
            f"Eligible collateral: {_fmt_money_any(eligible_collateral)}"
        )

        lines = [
            "DEAL WORKSHOP",
            "-------------",
            f"Transaction ID: {tx}",
            f"Company: {company_name}",
            "",
            "Application Summary",
            "-------------------",
            f"Amount requested: {_fmt_money_any(amount_requested)}",
            "",
            "Eligible Collateral (AR workshopping)",
            "-------------------------------------",
            f"Advance rate (%): {adv_pct}",
            f"Selected total amount (original): {_fmt_money_any(selected_total)}",
            f"Available funds (original): {_fmt_money_any(available_old)}",
            "",
            "Rejected invoices adjustment",
            "-----------------------------",
            f"Rejected invoices count: {rejected_count}",
            f"Rejected face value total: {_fmt_money_any(rejected_total)}",
            f"Selected total amount (adjusted): {_fmt_money_any(adjusted_selected)}",
            f"Available funds (recalculated): {_fmt_money_any(eligible_collateral)}",
        ]

        if include_linked:
            lines.append("")
            lines += _fmt_links_block(links, link_description)

        # Financial Statement Notes (still deterministic)
        try:
            fin_full = _fetch_financial_full_for_tx(tx, abn_digits=abn_digits)
            fs_notes = fin_full.get("fs_notes") or []
            fin_items = fin_full.get("items") or []
        except Exception as e:
            fs_notes = []
            fin_items = []
            lines.append("")
            lines.append("Financial Statement Notes (User)")
            lines.append("------------------------------")
            lines.append(f"⚠️ Unable to fetch financial notes from data service: {e}")
            lines.append("")
            fs_notes_payload = {"fs_notes": [], "items_notes": []}
        else:
            lines.append("")
            lines.append("Financial Statement Notes (User)")
            lines.append("------------------------------")
            if fs_notes:
                for n in fs_notes:
                    k = (n.get("financial_data_type") or "General").strip()
                    when = (n.get("updated_at") or n.get("created_at") or "")[:19]
                    note_body = (n.get("notes") or "").rstrip()
                    lines.append(f"- [{when}] {k}:")
                    lines.append(note_body if note_body else "(empty)")
                    lines.append("")
            else:
                lines.append("(none)")
                lines.append("")

            any_year_notes = False
            items_notes = []
            for it in fin_items:
                year = it.get("year") or "—"
                yr_notes = (it.get("financial_statement_notes") or "").strip()
                if yr_notes:
                    items_notes.append({"year": year, "financial_statement_notes": yr_notes})
                    if not any_year_notes:
                        lines.append("Notes to Financial Statements (by year)")
                        lines.append("----------------------------------------")
                        any_year_notes = True
                    lines.append(f"=== Year {year} ===")
                    lines.append(yr_notes)
                    lines.append("")
            fs_notes_payload = {"fs_notes": fs_notes, "items_notes": items_notes}

        lines.append("")
        lines.append("Rejected debtors (DebtorsCreditReport)")
        lines.append("--------------------------------------")
        if rejected_debtors:
            for d in rejected_debtors:
                name = (d.get("debtor_name") or "—").strip()
                deb_abn = (d.get("debtor_abn") or d.get("abn") or "—").strip()
                st = (d.get("state") or "—").strip()
                lines.append(f"- {name} (ABN: {deb_abn}) [state={st}]")
        else:
            lines.append("No rejected debtors recorded for this transaction.")

        lines += ["", "Conclusion", "----------", conclusion]

        raw_report = "\n".join(lines).rstrip()

        data_payload = {
            "aggregate": agg_js,
            "ar_snapshot": ar_js,
            "rejected_invoices": rej_js,
            "calculation": {
                "advance_rate_pct": str(adv_pct),
                "selected_total_original": str(selected_total),
                "rejected_face_value_total": str(rejected_total),
                "selected_total_adjusted": str(adjusted_selected),
                "eligible_collateral": str(eligible_collateral),
                "amount_requested": str(amount_requested),
                "comparison": f"amount_requested {cmp_symbol} eligible_collateral",
                "rejected_debtors_count": str(rejected_debtors_count),
            },
            "linking": {
                "include_linked_entities": include_linked,
                "links": links,
                "link_description": link_description,
            },
            "financial_statement_notes": fs_notes_payload,
        }

        return JsonResponse({"ok": True, "report": raw_report, "data": data_payload}, status=200)

    # =====================================================================
    # FALLBACK
    # =====================================================================
    return JsonResponse({"ok": False, "error": f"Unknown kind '{kind}'"}, status=400)

import requests
from django.conf import settings
from django.views.decorators.http import require_GET
from django.http import JsonResponse

@require_GET
def financial_summary_proxy(request, abn):
    abn_digits = "".join(ch for ch in (abn or "") if ch.isdigit())
    if not abn_digits:
        return JsonResponse({"ok": False, "error": "ABN is required"}, status=400)

    url = f"{settings.EFS_DATA_FINANCIAL_BASE_URL}/financial/summary/{abn_digits}/"
    try:
        r = requests.get(
            url,
            headers={"X-Internal-Key": settings.INTERNAL_API_KEY},
            timeout=getattr(settings, "REQUESTS_DEFAULT_TIMEOUT", 15),
        )
        return JsonResponse(r.json(), status=r.status_code, safe=False)
    except requests.RequestException as e:
        return JsonResponse({"ok": False, "error": str(e)}, status=502)





# ---- End of Agents Modal code that interacts with in efs_sales & efs_data_financials-----------------------------
# ---- End of Agents Modal code that interacts with in efs_sales & efs_data_financials-----------------------------
# ---- End of Agents Modal code that interacts with in efs_sales & efs_data_financials-----------------------------
# ---- End of Agents Modal code that interacts with in efs_sales & efs_data_financials-----------------------------
# ---- End of Agents Modal code that interacts with in efs_sales & efs_data_financials-----------------------------
















# ---- this is the code to generate the final report for investors-----
# ---- this is the code to generate the final report for investors-----
# ---- this is the code to generate the final report for investors-----
# ---- this is the code to generate the final report for investors-----
# ---- this is the code to generate the final report for investors-----




# efs_agents/core/views.py
# efs_agents/core/views.py

import json
import re
import logging
from typing import Any, List, Dict, Tuple, Optional

from django.conf import settings
from django.http import JsonResponse, HttpResponseBadRequest
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import csrf_exempt

import google.generativeai as genai

from .models import AgentSectionData, AgentTurnMemory

logger = logging.getLogger(__name__)

STM_LIMIT = 5

# Optional pgvector cosine distance for LTM similarity retrieval
try:
    from pgvector.django import CosineDistance
except Exception:
    try:
        from pgvector.django.functions import CosineDistance
    except Exception:
        CosineDistance = None


# ---------------------------------------------------------------------
# Gemini helpers
# ---------------------------------------------------------------------
def _get_gemini_model():
    api_key = getattr(settings, "GEMINI_API_KEY", None)
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY is not set")

    genai.configure(api_key=api_key)

    # NOTE: per your preference: do NOT use "models/" prefix
    model_name = getattr(settings, "GEMINI_MODEL_NAME", "gemini-2.0-flash")
    return genai.GenerativeModel(model_name)


def _fallback_model_name() -> str | None:
    try:
        models = list(genai.list_models())
        for m in models:
            if "generateContent" in getattr(m, "supported_generation_methods", []):
                if "gemini-1.5" in m.name:
                    return m.name
        for m in models:
            if "generateContent" in getattr(m, "supported_generation_methods", []):
                return m.name
    except Exception:
        pass
    return None


def _llm_complete(prompt: str, *, temperature=0.2, max_tokens=20000):
    try:
        model = _get_gemini_model()
        resp = model.generate_content(
            prompt,
            generation_config={"temperature": temperature, "max_output_tokens": max_tokens},
        )
        return (resp.text or "").strip(), None
    except Exception as e:
        fb = _fallback_model_name()
        if fb:
            try:
                resp = genai.GenerativeModel(fb).generate_content(
                    prompt,
                    generation_config={"temperature": temperature, "max_output_tokens": max_tokens},
                )
                return (resp.text or "").strip(), None
            except Exception as e2:
                return "", f"exception:{e2}"
        return "", f"exception:{e}"


# ---------------------------------------------------------------------
# Agent memory fetching  helpers 
# ---------------------------------------------------------------------


import json
from django.db.models import Q

from .models import (
    AgentSectionData,
    AgentTurnMemory,
    MemoryConfiguration,
    SemanticMemory,
    ProceduralMemory,
    FeedbackMemory,     # only if you want feedback in prompt
    EpisodicMemory,     # only if you want episodic in prompt
)


from typing import Any, Dict, List, Tuple, Optional
import logging

logger = logging.getLogger(__name__)

STM_LIMIT = 5

# Optional pgvector cosine distance for LTM similarity retrieval
try:
    from pgvector.django import CosineDistance
except Exception:
    try:
        from pgvector.django.functions import CosineDistance
    except Exception:
        CosineDistance = None


def _digits_only(s: str) -> str:
    return "".join(ch for ch in str(s or "") if ch.isdigit())


def _head_tail(s: str, n: int = 350) -> str:
    s = (s or "").strip()
    if len(s) <= n * 2:
        return s
    return s[:n] + "\n...\n" + s[-n:]


def _embedding_field_name() -> Optional[str]:
    """
    Your AgentTurnMemory fields (from your error message) include:
      - embedding
      - output_embedding

    We prefer output_embedding for "output_text" similarity search.
    """
    for name in ("output_embedding", "embedding"):
        try:
            AgentTurnMemory._meta.get_field(name)
            return name
        except Exception:
            continue
    return None

def _semantic_embedding_field_name() -> Optional[str]:
    # Prefer value_embedding (usually richer), fallback to key_embedding
    for name in ("value_embedding", "key_embedding"):
        try:
            SemanticMemory._meta.get_field(name)
            return name
        except Exception:
            continue
    return None


def _procedural_embedding_field_name() -> Optional[str]:
    try:
        ProceduralMemory._meta.get_field("embedding")
        return "embedding"
    except Exception:
        return None


def _safe_float(v, default=0.7) -> float:
    try:
        return float(v)
    except Exception:
        return default


def _semantic_rows_to_text(rows: list[SemanticMemory]) -> str:
    if not rows:
        return ""
    lines = ["SEMANTIC MEMORY (retrieved)"]
    for r in rows:
        meta = r.metadata if isinstance(r.metadata, dict) else None
        meta_txt = f" | meta={json.dumps(meta, ensure_ascii=False)}" if meta else ""
        lines.append(f"- [{r.category}] {r.key} = {r.value}{meta_txt}")
    return "\n".join(lines).strip()


def _procedural_rows_to_text(rows: list[ProceduralMemory]) -> str:
    if not rows:
        return ""
    lines = ["PROCEDURAL MEMORY (retrieved)"]
    for r in rows:
        meta = r.metadata if isinstance(r.metadata, dict) else None
        meta_txt = f" | meta={json.dumps(meta, ensure_ascii=False)}" if meta else ""
        lines.append(f"- ({r.rule_type}) {r.rule_name}: IF {r.condition_expression} THEN {r.action}{meta_txt}")
    return "\n".join(lines).strip()





# IMPORTANT:
# You must already have _embed_text(text)->Optional[list[float]]
# that returns the correct dimension for your VectorField.
# (You already built this earlier in your project.)
#
# def _embed_text(text: str) -> Optional[list[float]]:
#     ...


# ---------------------------------------------------------------------
# MEMORY GATHER (UPDATED)
# - returns (memory_text, trace)
# - STM prefers tx matches, then abn matches, then fill
# - LTM uses similarity if embeddings available, else recency
# - includes head+tail so your stored marker text is hard to miss
# ---------------------------------------------------------------------

# NOTE: you must already have _embed_text(text)->Optional[list[float]]
# that returns the correct dimension for your VectorField.
# def _embed_text(text: str) -> Optional[list[float]]:
#     ...


def _gather_agent_memory_stm_ltm(
    agent: AgentSectionData,
    *,
    query_text: str = "",
    k_ltm: int = 6,
    tx: str = "",
    abn: str = "",
) -> Tuple[str, Dict[str, Any]]:
    """
    Returns: (memory_text, trace)

    Uses AgentTurnMemory fields:
      - tier (STM/LTM selector)
      - input_text / output_text / compressed_text
      - output_embedding (preferred) / embedding
      - kind, ticket_label, transaction_id, abn, created_at

    Tier values:
      We support a few common strings to avoid breakage.
      Adjust these if you want to standardize.
    """
    STM_TIERS = ("stm", "stm_turn", "short", "short_term")
    LTM_TIERS = ("ltm", "ltm_turn", "long", "long_term")

    parts: List[str] = []
    trace: Dict[str, Any] = {
        "stm_ids": [],
        "ltm_ids": [],
        "stm_count": 0,
        "ltm_count": 0,
        "stm_tx_count": 0,
        "stm_abn_count": 0,
        "ltm_mode": None,          # "similarity" | "recency" | None
        "embedding_used": False,
        "embedding_field": None,
    }

    tx = (tx or "").strip()
    abn = _digits_only(abn or "")
    query_text = (query_text or "").strip()

    # -----------------------
    # STM: prefer tx rows, then abn rows, then fill
    # -----------------------
    stm_qs = AgentTurnMemory.objects.filter(agent=agent, tier__in=STM_TIERS)

    stm_rows: List[AgentTurnMemory] = []

    if tx:
        tx_rows = list(stm_qs.filter(transaction_id=tx).order_by("-created_at")[:STM_LIMIT])
        stm_rows.extend(tx_rows)
        trace["stm_tx_count"] = len(tx_rows)

    if len(stm_rows) < STM_LIMIT and abn:
        existing = {r.id for r in stm_rows}
        abn_rows = list(
            stm_qs.filter(abn=abn)
                  .exclude(id__in=existing)
                  .order_by("-created_at")[: (STM_LIMIT - len(stm_rows))]
        )
        stm_rows.extend(abn_rows)
        trace["stm_abn_count"] = len(abn_rows)

    if len(stm_rows) < STM_LIMIT:
        existing = {r.id for r in stm_rows}
        fill_rows = list(
            stm_qs.exclude(id__in=existing)
                  .order_by("-created_at")[: (STM_LIMIT - len(stm_rows))]
        )
        stm_rows.extend(fill_rows)

    trace["stm_ids"] = [str(r.id) for r in stm_rows]
    trace["stm_count"] = len(stm_rows)

    if stm_rows:
        parts.append("SHORT-TERM MEMORY (most recent turns)")
        for r in reversed(stm_rows):
            parts.append(f"- [{r.created_at:%Y-%m-%d %H:%M}] {(r.kind or '?')} / {(r.ticket_label or '?')}")

            inp = (r.input_text or "").strip()
            out = (r.output_text or "").strip()

            # head+tail makes your marker text much harder to miss
            parts.append("  INPUT:\n" + _head_tail(inp))
            parts.append("  OUTPUT:\n" + _head_tail(out))
            parts.append("")

    # -----------------------
    # LTM
    # -----------------------
    if not query_text:
        return "\n".join(parts).strip(), trace

    emb_field = _embedding_field_name()
    trace["embedding_field"] = emb_field

    ltm_qs_base = AgentTurnMemory.objects.filter(agent=agent, tier__in=LTM_TIERS)

    q_emb = None
    if emb_field:
        try:
            q_emb = _embed_text(query_text)  # must exist in your module
        except Exception as e:
            logger.warning("Embedding failed; skipping similarity LTM: %s", e)
            q_emb = None

    ltm_rows: List[AgentTurnMemory] = []

    if q_emb and CosineDistance is not None and emb_field:
        trace["embedding_used"] = True
        trace["ltm_mode"] = "similarity"
        try:
            ltm_rows = list(
                ltm_qs_base.filter(**{f"{emb_field}__isnull": False})
                           .annotate(dist=CosineDistance(emb_field, q_emb))
                           .order_by("dist")[:k_ltm]
            )
        except Exception as e:
            logger.warning("LTM similarity query failed; falling back to recency: %s", e)
            ltm_rows = []

    if not ltm_rows:
        trace["ltm_mode"] = trace["ltm_mode"] or "recency"
        ltm_rows = list(ltm_qs_base.order_by("-created_at")[:k_ltm])

    trace["ltm_ids"] = [str(r.id) for r in ltm_rows]
    trace["ltm_count"] = len(ltm_rows)

    if ltm_rows:
        parts.append("LONG-TERM MEMORY")
        for r in reversed(ltm_rows):
            # Prefer compressed_text if you’re storing it; else output_text.
            txt = (r.compressed_text or r.output_text or "").strip()
            parts.append(f"- {(r.kind or '?')} / {(r.ticket_label or '?')}: {txt[:800]}")

    return "\n".join(parts).strip(), trace


import re
from django.db.models import Q

def _keywords_from_text(t: str, max_terms: int = 12) -> list[str]:
    """
    Extracts a small set of useful keyword terms from a long report.
    Helps keyword fallback retrieval actually match your stored memories.
    """
    t = (t or "").lower()
    words = re.findall(r"[a-z0-9]{4,}", t)  # keep 4+ chars
    stop = {
        "this","that","with","from","have","will","your","into","over","they","them","then",
        "than","been","were","which","also","only","report","draft","credit","analysis"
    }
    words = [w for w in words if w not in stop]

    seen = set()
    out: list[str] = []
    for w in words:
        if w in seen:
            continue
        seen.add(w)
        out.append(w)
        if len(out) >= max_terms:
            break
    return out



def _build_sources_banner(
    *,
    agent: AgentSectionData,
    memory_trace: dict | None,
    config_trace: dict | None,
    show_ids: bool = False,          # ✅ default hides IDs (cleaner)
    max_ids: int = 5,                # ✅ cap if you enable show_ids
) -> tuple[str, dict]:
    """
    Returns:
      (banner_text, sources_used_dict)

    Banner is designed to be human-readable and compact.
    IDs are hidden by default; turn on show_ids for deeper debugging.
    """

    bot = (getattr(agent, "bot_name", "") or "Agent").strip()
    agent_id = str(getattr(agent, "id", "") or "")

    # --- Turn memory ---
    stm_count = int((memory_trace or {}).get("stm_count", 0) or 0)
    ltm_count = int((memory_trace or {}).get("ltm_count", 0) or 0)
    ltm_mode  = (memory_trace or {}).get("ltm_mode")
    stm_ids   = [str(x) for x in (memory_trace or {}).get("stm_ids", [])]
    ltm_ids   = [str(x) for x in (memory_trace or {}).get("ltm_ids", [])]
    turn_used = bool(stm_count or ltm_count)

    # --- Config memory ---
    cfg_used = bool((config_trace or {}).get("has_config"))
    cfg_id   = (config_trace or {}).get("config_id")
    sem_count = int((config_trace or {}).get("semantic_count", 0) or 0)
    sem_mode  = (config_trace or {}).get("semantic_mode")
    sem_ids   = [str(x) for x in (config_trace or {}).get("semantic_ids", [])]

    proc_count = int((config_trace or {}).get("procedural_count", 0) or 0)
    proc_mode  = (config_trace or {}).get("procedural_mode")
    proc_ids   = [str(x) for x in (config_trace or {}).get("procedural_ids", [])]

    # ---------
    # Compact lines (no IDs by default)
    # ---------
    lines = []
    lines.append("\n\n---")
    lines.append("### Sources used (prompt injection provenance)")
    lines.append(f"- **Agent:** {bot}")

    if turn_used:
        mode_txt = f", LTM mode: {ltm_mode}" if ltm_mode else ""
        lines.append(f"- **Conversation memory (AgentTurnMemory):** STM {stm_count}, LTM {ltm_count}{mode_txt}")
        if show_ids:
            if stm_ids:
                lines.append(f"  - STM ids: {', '.join(stm_ids[:max_ids])}" + (" …" if len(stm_ids) > max_ids else ""))
            if ltm_ids:
                lines.append(f"  - LTM ids: {', '.join(ltm_ids[:max_ids])}" + (" …" if len(ltm_ids) > max_ids else ""))
    else:
        lines.append("- **Conversation memory (AgentTurnMemory):** not used")

    if cfg_used:
        lines.append(f"- **Memory configuration:** {cfg_id}")
        lines.append(f"- **Semantic memory:** {sem_count} item(s)" + (f" (mode: {sem_mode})" if sem_mode else ""))
        lines.append(f"- **Procedural memory:** {proc_count} item(s)" + (f" (mode: {proc_mode})" if proc_mode else ""))
        if show_ids:
            if sem_ids:
                lines.append(f"  - Semantic ids: {', '.join(sem_ids[:max_ids])}" + (" …" if len(sem_ids) > max_ids else ""))
            if proc_ids:
                lines.append(f"  - Procedural ids: {', '.join(proc_ids[:max_ids])}" + (" …" if len(proc_ids) > max_ids else ""))
    else:
        lines.append("- **Memory configuration / semantic / procedural:** not used")

    # Optional: keep the full structured truth for UI / logs
    sources_used = {
        "agent": {"bot_name": bot, "id": agent_id},
        "agent_turn_memory": {
            "used": turn_used,
            "stm_count": stm_count,
            "ltm_count": ltm_count,
            "ltm_mode": ltm_mode,
            "stm_ids": stm_ids,
            "ltm_ids": ltm_ids,
        },
        "memory_configuration": {
            "used": cfg_used,
            "config_id": cfg_id,
        },
        "semantic_memory": {
            "used": sem_count > 0,
            "count": sem_count,
            "mode": sem_mode,
            "ids": sem_ids,
        },
        "procedural_memory": {
            "used": proc_count > 0,
            "count": proc_count,
            "mode": proc_mode,
            "ids": proc_ids,
        },
    }

    banner = "\n".join(lines).rstrip() + "\n"
    return banner, sources_used

def _gather_agent_config_memory(
    agent: AgentSectionData,
    *,
    query_text: str,
    k_semantic: int = 6,
    k_procedural: int = 6,
) -> Tuple[str, Dict[str, Any]]:
    """
    Pulls relevant SemanticMemory + ProceduralMemory for the agent.
    Returns (text_block, trace).
    """
    trace: Dict[str, Any] = {
        "has_config": False,
        "config_id": None,
        "semantic_mode": None,     # "similarity" | "keyword" | "none"
        "procedural_mode": None,   # "similarity" | "keyword" | "none"
        "semantic_ids": [],
        "procedural_ids": [],
        "semantic_count": 0,
        "procedural_count": 0,
        "semantic_enabled_effective": False,
        "procedural_enabled_effective": False,
        "keywords_used": [],
    }

    cfg = getattr(agent, "memory_config", None)
    if not cfg:
        return "", trace

    trace["has_config"] = True
    trace["config_id"] = str(cfg.id)

    query_text = (query_text or "").strip()
    if not query_text:
        return "", trace

    # Base filters: config-scoped OR agent-specific seeds
    sem_base = SemanticMemory.objects.filter(Q(config=cfg) | Q(agent=agent))
    proc_base = ProceduralMemory.objects.filter(Q(config=cfg) | Q(agent=agent))

    # Effective toggles: respect config flags, but also treat as enabled if rows exist
    sem_on = bool(getattr(cfg, "semantic_enabled", False)) or sem_base.exists()
    proc_on = bool(getattr(cfg, "procedural_enabled", False)) or proc_base.exists()
    trace["semantic_enabled_effective"] = sem_on
    trace["procedural_enabled_effective"] = proc_on

    # If neither has any rows, bail early
    if not sem_on and not proc_on:
        trace["semantic_mode"] = "none"
        trace["procedural_mode"] = "none"
        return "", trace

    relevance_threshold = _safe_float(getattr(cfg, "ltm_relevance_threshold", 0.7), 0.7)

    # -------------------
    # SEMANTIC retrieval
    # -------------------
    semantic_rows: list[SemanticMemory] = []
    if sem_on:
        sem_emb_field = _semantic_embedding_field_name()
        q_emb = None

        if sem_emb_field:
            try:
                q_emb = _embed_text(query_text)
            except Exception as e:
                logger.warning("Config semantic embedding failed: %s", e)
                q_emb = None

        if q_emb and CosineDistance is not None and sem_emb_field:
            trace["semantic_mode"] = "similarity"
            try:
                qs = (
                    sem_base.filter(**{f"{sem_emb_field}__isnull": False})
                            .annotate(dist=CosineDistance(sem_emb_field, q_emb))
                            .order_by("dist")[: (k_semantic * 3)]
                )
                max_dist = max(0.0, 1.0 - relevance_threshold)
                semantic_rows = [r for r in qs if getattr(r, "dist", 1.0) <= max_dist][:k_semantic]
            except Exception as e:
                logger.warning("Semantic similarity query failed; fallback to keyword: %s", e)
                semantic_rows = []

        if not semantic_rows:
            trace["semantic_mode"] = trace["semantic_mode"] or "keyword"
            terms = _keywords_from_text(query_text)
            trace["keywords_used"] = terms

            q = Q()
            for term in terms:
                q |= Q(category__icontains=term) | Q(key__icontains=term) | Q(value__icontains=term)

            if q:
                semantic_rows = list(sem_base.filter(q).order_by("-created_at")[:k_semantic])
            else:
                semantic_rows = list(sem_base.order_by("-created_at")[:k_semantic])

    trace["semantic_ids"] = [str(r.id) for r in semantic_rows]
    trace["semantic_count"] = len(semantic_rows)

    # ---------------------
    # PROCEDURAL retrieval
    # ---------------------
    procedural_rows: list[ProceduralMemory] = []
    if proc_on:
        proc_emb_field = _procedural_embedding_field_name()
        q_emb2 = None

        if proc_emb_field:
            try:
                q_emb2 = _embed_text(query_text)
            except Exception as e:
                logger.warning("Config procedural embedding failed: %s", e)
                q_emb2 = None

        if q_emb2 and CosineDistance is not None and proc_emb_field:
            trace["procedural_mode"] = "similarity"
            try:
                qs = (
                    proc_base.filter(embedding__isnull=False)
                             .annotate(dist=CosineDistance("embedding", q_emb2))
                             .order_by("dist")[: (k_procedural * 3)]
                )
                max_dist = max(0.0, 1.0 - relevance_threshold)
                procedural_rows = [r for r in qs if getattr(r, "dist", 1.0) <= max_dist][:k_procedural]
            except Exception as e:
                logger.warning("Procedural similarity query failed; fallback to keyword: %s", e)
                procedural_rows = []

        if not procedural_rows:
            trace["procedural_mode"] = trace["procedural_mode"] or "keyword"
            terms = _keywords_from_text(query_text)
            # keep keywords_used if semantic didn't set it
            if not trace.get("keywords_used"):
                trace["keywords_used"] = terms

            q = Q()
            for term in terms:
                q |= (
                    Q(rule_name__icontains=term) |
                    Q(condition_expression__icontains=term) |
                    Q(action__icontains=term)
                )

            if q:
                procedural_rows = list(proc_base.filter(q).order_by("-id")[:k_procedural])
            else:
                procedural_rows = list(proc_base.order_by("-id")[:k_procedural])

    trace["procedural_ids"] = [str(r.id) for r in procedural_rows]
    trace["procedural_count"] = len(procedural_rows)

    # ---------------------
    # Render blocks
    # ---------------------
    blocks: list[str] = []
    sem_txt = _semantic_rows_to_text(semantic_rows) if sem_on and semantic_rows else ""
    proc_txt = _procedural_rows_to_text(procedural_rows) if proc_on and procedural_rows else ""

    if sem_txt:
        blocks.append(sem_txt)
    if proc_txt:
        blocks.append(proc_txt)

    return "\n\n".join(blocks).strip(), trace


# ---------------------------------------------------------------------
# SAVE helper (assumed)
# You said you already have save_turn_memory(...) for AgentTurnMemory.
# Keep your existing implementation.
# ---------------------------------------------------------------------
# def save_turn_memory(...): ...


# ---------------------------------------------------------------------
# REPORT GENERATION (UPDATED per the “proof” / “debug_memory” approach)
# - memory injected with explicit START/END delimiters
# - optional debug_memory returns memory_preview + trace
# - optional debug_memory also forces LLM to *acknowledge* memory presence
# ---------------------------------------------------------------------
# views.py (UPDATED generate_credit_report with deterministic “sources used” banner)

@csrf_exempt
@require_POST
def generate_credit_report(request):
    try:
        payload: dict[str, Any] = json.loads(request.body.decode("utf-8") or "{}")
    except Exception:
        return HttpResponseBadRequest("Invalid JSON")

    base_report = (payload.get("report") or "").strip()
    abn = (payload.get("abn") or "").strip()
    tx = (payload.get("transaction_id") or "").strip()
    include_linked = bool(payload.get("include_linked_entities"))

    agent_id = (payload.get("agent_id") or "").strip()
    kind = (payload.get("kind") or "credit_report").strip().lower()
    ticket_label = (payload.get("ticket_label") or "Credit Report").strip()

    debug_memory = _boolish(payload.get("debug_memory"))
    show_sources = _boolish(payload.get("show_sources", True))  # ✅ NEW (default ON)

    if not base_report:
        return JsonResponse({"error": "Report text is empty."}, status=400)

    # ----------------------------
    # MEMORY LOAD (AgentTurnMemory STM/LTM)
    # ----------------------------
    agent = None
    memory_text = ""
    memory_trace = None

    if agent_id:
        try:
            agent = AgentSectionData.objects.get(id=agent_id)
        except AgentSectionData.DoesNotExist:
            return JsonResponse({"error": "Selected agent not found."}, status=404)

        try:
            memory_text, memory_trace = _gather_agent_memory_stm_ltm(
                agent,
                query_text=base_report,
                tx=tx,
                abn=_digits_only(abn),
            )
        except Exception as e:
            logger.warning("Memory gather failed (continuing without memory): %s", e)
            memory_text = ""
            memory_trace = None

    # ----------------------------
    # CONFIG MEMORY LOAD (Semantic + Procedural)
    # ----------------------------
    config_memory_text = ""
    config_memory_trace = None
    if agent:
        try:
            config_memory_text, config_memory_trace = _gather_agent_config_memory(
                agent,
                query_text=base_report,
                k_semantic=6,
                k_procedural=6,
            )
        except Exception as e:
            logger.warning("Config memory gather failed: %s", e)
            config_memory_text = ""
            config_memory_trace = None

    # ----------------------------
    # Extract guidance inside """ ... """
    # ----------------------------
    guidance_blocks: List[str] = []

    def _guidance_replacer(match: re.Match) -> str:
        inner = (match.group(1) or "").strip()
        if inner:
            guidance_blocks.append(inner)
        return ""

    cleaned_report = re.sub(r'"""([\s\S]*?)"""', _guidance_replacer, base_report)
    if not cleaned_report.strip():
        cleaned_report = base_report

    if guidance_blocks:
        guidance_text = "\n".join(f"- {g}" for g in guidance_blocks)
        extra_instructions = (
            "EXTRA INSTRUCTIONS (high priority if consistent with credit practice):\n"
            f"{guidance_text}\n\n"
        )
    else:
        extra_instructions = ""

    persona = (getattr(agent, "persona", "") or "").strip() if agent else ""
    bot_name = (getattr(agent, "bot_name", "") or "Agent").strip() if agent else "Agent"

    # ----------------------------
    # Build memory block with delimiters (proof it was injected)
    # ----------------------------
    memory_block = ""
    if memory_text or config_memory_text:
        memory_block = (
            "MEMORY CONTEXT START\n"
            + (memory_text + "\n\n" if memory_text else "")
            + (config_memory_text + "\n" if config_memory_text else "")
            + "MEMORY CONTEXT END\n\n"
        )

    # ----------------------------
    # Optional LLM debug ACK
    # ----------------------------
    debug_instruction = ""
    if debug_memory:
        debug_instruction = (
            "DEBUG INSTRUCTION:\n"
            "Before writing the report, output ONE line:\n"
            "MEMORY_ACK=<YES|NO> ; STM=<n> ; LTM=<n> ; CFG=<YES|NO> ; PROC=<n> ; SEM=<n>\n"
            "Then write the report normally.\n\n"
        )
        if memory_trace:
            debug_instruction += (
                f"(System debug counts: STM={memory_trace.get('stm_count',0)} ; "
                f"LTM={memory_trace.get('ltm_count',0)})\n\n"
            )

    # ----------------------------
    # Prompt
    # ----------------------------
    prompt = (
        f"You are {bot_name}, an experienced commercial credit analyst.\n\n"
        + (f"PERSONA:\n{persona}\n\n" if persona else "")
        + memory_block
        + debug_instruction
        + extra_instructions
        + "Rewrite the following draft into a concise, professional credit report.\n"
          "- Start with an 'Executive Summary', then 'Financial Performance', "
          "'Working Capital', 'Asset Base & Security', 'Funding Capacity', and 'Recommendation'.\n"
          "- Include one small metrics table if helpful.\n"
          "- Do NOT invent numbers or facts; only rephrase and organize what is present.\n"
          "- If include_linked_entities is true, only incorporate linked entities that already appear in the draft.\n"
          "- Audience is a credit/risk/sales analyst.\n\n"
        f"ABN: {abn or '—'}\n"
        f"Transaction ID: {tx or '—'}\n"
        f"include_linked_entities: {include_linked}\n\n"
        "===== DRAFT =====\n"
        f"{cleaned_report}\n"
        "===== END DRAFT =====\n"
    )

    out, err = _llm_complete(prompt, temperature=0.2, max_tokens=20000)
    if err:
        return JsonResponse({"error": f"LLM failure: {err}"}, status=502)

    out = (out or "").strip()

    # ----------------------------
    # ✅ Deterministic “Sources Used” banner (server truth)
    # ----------------------------
    sources_used = None
    if show_sources and agent:
        try:
            banner, sources_used = _build_sources_banner(
                agent=agent,
                memory_trace=memory_trace,
                config_trace=config_memory_trace,
            )
            out = out + banner
        except Exception as e:
            logger.warning("Sources banner build failed: %s", e)

    # ----------------------------
    # Response
    # ----------------------------
    resp: Dict[str, Any] = {
        "report": out,
        "agent_summary": {
            "agent": bot_name,
            "kind": kind,
            "ticket_label": ticket_label,
        },
        "memory_used": bool(memory_text or config_memory_text),
    }

    # Optional structured sources for UI (recommended)
    if show_sources and sources_used is not None:
        resp["sources_used"] = sources_used

    # Only return deep memory proof when explicitly requested
    if debug_memory:
        resp["memory_debug"] = {
            **(memory_trace or {}),
            "turn_memory_preview": (memory_text or "")[:2000],
            "turn_memory_chars": len(memory_text or ""),
            "config_memory_preview": (config_memory_text or "")[:4000],
            "config_memory_chars": len(config_memory_text or ""),
            "config_trace": config_memory_trace or {},
        }

    return JsonResponse(resp)





# =====================================================================
    # Save agent report in vector DB 
# =====================================================================



@csrf_exempt
@require_POST
def api_agents_memory_save(request):
    """
    POST /api/agents/memory/save/
    Saves STM and auto-promotes overflow to LTM.
    """
    try:
        payload = json.loads(request.body.decode("utf-8") or "{}")
    except Exception:
        return JsonResponse({"ok": False, "error": "Invalid JSON"}, status=400)

    agent_id = (payload.get("agent_id") or "").strip()
    if not agent_id:
        return JsonResponse({"ok": False, "error": "agent_id is required"}, status=400)

    output_text = (payload.get("output_text") or "").strip()
    if not output_text:
        return JsonResponse({"ok": False, "error": "output_text is required"}, status=400)

    kind = (payload.get("kind") or "general").strip().lower()
    ticket_label = (payload.get("ticket_label") or "Saved Report").strip()
    abn = _digits_only(payload.get("abn") or "")
    tx = (payload.get("transaction_id") or "").strip()

    input_text = (payload.get("input_text") or "").strip()
    source = (payload.get("source") or "ui_save_button").strip()

    try:
        agent = AgentSectionData.objects.get(id=agent_id)
    except AgentSectionData.DoesNotExist:
        return JsonResponse({"ok": False, "error": "Selected agent not found"}, status=404)

    try:
        save_turn_memory(
            agent=agent,
            kind=kind,
            ticket_label=ticket_label,
            abn=abn,
            tx=tx,
            input_text=input_text,
            output_text=output_text,
            metadata={
                "source": source,
                "include_linked_entities": _boolish(payload.get("include_linked_entities")),
            },
        )
    except Exception as e:
        logger.exception("Memory save failed")
        return JsonResponse({"ok": False, "error": f"Memory save failed: {e}"}, status=500)

    return JsonResponse({"ok": True})



from datetime import timedelta
from django.db import transaction
from django.utils import timezone

def save_turn_memory(
    *,
    agent: AgentSectionData,
    kind: str,
    ticket_label: str,
    abn: str,
    tx: str,
    input_text: str,
    output_text: str,
    metadata: dict | None = None,
):
    """
    Writes 1 STM row to AgentTurnMemory.
    Promotes oldest STM rows to LTM when STM exceeds STM_LIMIT.

    Fixes:
    - Embeddings written to BOTH `output_embedding` and `embedding` if present.
    - Uses `tier` (NOT `category`) to match your model fields.
    - Prevents accidental double-saves (same payload within 3 seconds).
    """
    kind = (kind or "general").strip().lower()
    ticket_label = (ticket_label or "Saved Report").strip()
    abn = _digits_only(abn or "")
    tx = (tx or "").strip()

    out_clean = (output_text or "").strip()
    in_clean = (input_text or "").strip()
    if not out_clean:
        return

    meta = dict(metadata or {})
    meta.update({
        "kind": kind,
        "ticket_label": ticket_label,
        "abn": abn,
        "transaction_id": tx,
        "saved_at": timezone.now().isoformat(),
    })

    # ---------
    # DEDUPE: avoid “2 rows per click” if your JS binds twice
    # ---------
    recent_window = timezone.now() - timedelta(seconds=3)
    dup_qs = AgentTurnMemory.objects.filter(
        agent=agent,
        tier="stm",
        kind=kind,
        ticket_label=ticket_label,
        abn=abn,
        transaction_id=tx,
        output_text=out_clean,
        created_at__gte=recent_window,
    )
    if dup_qs.exists():
        logger.warning("Deduped duplicate save_turn_memory within 3s window.")
        return

    # ---------
    # EMBED STM
    # ---------
    stm_vec = _embed_text(
        f"{kind}\n{ticket_label}\nTX:{tx}\nABN:{abn}\n\nOUTPUT:\n{out_clean}"
    )

    # detect which fields exist
    has_embedding = True
    try:
        AgentTurnMemory._meta.get_field("embedding")
    except Exception:
        has_embedding = False

    has_output_embedding = True
    try:
        AgentTurnMemory._meta.get_field("output_embedding")
    except Exception:
        has_output_embedding = False

    has_compressed_text = True
    try:
        AgentTurnMemory._meta.get_field("compressed_text")
    except Exception:
        has_compressed_text = False

    with transaction.atomic():
        # 1) Create STM
        create_kwargs = dict(
            agent=agent,
            tier="stm",
            kind=kind,
            ticket_label=ticket_label,
            abn=abn,
            transaction_id=tx,
            input_text=in_clean,
            output_text=out_clean,
            metadata=meta,
        )
        # write vectors wherever possible
        if has_embedding:
            create_kwargs["embedding"] = stm_vec
        if has_output_embedding:
            create_kwargs["output_embedding"] = stm_vec

        AgentTurnMemory.objects.create(**create_kwargs)

        # 2) Promote overflow STM -> LTM
        stm_qs = (
            AgentTurnMemory.objects
            .select_for_update()
            .filter(agent=agent, tier="stm")
            .order_by("created_at")
        )

        excess = stm_qs.count() - STM_LIMIT
        if excess > 0:
            promote_rows = list(stm_qs[:excess])

            for row in promote_rows:
                compressed = _compress_turn(
                    row.kind or kind,
                    row.ticket_label or ticket_label,
                    row.input_text or "",
                    row.output_text or "",
                ).strip()

                ltm_vec = _embed_text(compressed) if compressed else None

                row.tier = "ltm"
                row.input_text = ""  # drop bulky input for LTM

                if has_compressed_text:
                    row.compressed_text = compressed
                row.output_text = compressed  # keep compressed in output_text for easy rendering/search

                if has_embedding:
                    row.embedding = ltm_vec
                if has_output_embedding:
                    row.output_embedding = ltm_vec

                row.metadata = {
                    "kind": row.kind,
                    "ticket_label": row.ticket_label,
                    "abn": row.abn,
                    "transaction_id": row.transaction_id,
                    "source": "compressed_from_stm",
                    "compressed_at": timezone.now().isoformat(),
                    "origin_id": str(row.id),
                }

                update_fields = ["tier", "input_text", "output_text", "metadata"]
                if has_compressed_text:
                    update_fields.append("compressed_text")
                if has_embedding:
                    update_fields.append("embedding")
                if has_output_embedding:
                    update_fields.append("output_embedding")

                row.save(update_fields=update_fields)

        # 3) Optional: cap LTM growth
        if LTM_LIMIT and LTM_LIMIT > 0:
            ltm_qs = (
                AgentTurnMemory.objects
                .select_for_update()
                .filter(agent=agent, tier="ltm")
                .order_by("-created_at")
            )
            ids_keep = list(ltm_qs.values_list("id", flat=True)[:LTM_LIMIT])
            (
                AgentTurnMemory.objects
                .filter(agent=agent, tier="ltm")
                .exclude(id__in=ids_keep)
                .delete()
            )

# =====================================================================
# efs_risk service code 
# =====================================================================




from django.shortcuts import render
from django.views.decorators.http import require_GET

from .models import AgentSectionData  # ✅ correct model


@require_GET
def risk_agents_modal(request):
    """
    Returns rendered HTML for the Risk Agents modal.
    Called by efs_risk (BFF).
    """
    abn = request.GET.get("abn", "") or ""
    tx  = request.GET.get("tx", "") or ""

    saved_agents = AgentSectionData.objects.all().order_by("bot_name")

    return render(request, "risk_agents.html", {
        "abn": abn,
        "tx": tx,
        "saved_agents": saved_agents,
    })




   # =====================================================================
   # efs_operations service code 
   # =====================================================================



@require_GET
def operations_agents_modal(request):
    abn = request.GET.get("abn", "") or ""
    tx  = request.GET.get("tx", "") or ""

    saved_agents = AgentSectionData.objects.all().order_by("bot_name")

    return render(request, "ops_agents.html", {
        "abn": abn,
        "tx": tx,
        "saved_agents": saved_agents,
    })




   # =====================================================================
   # efs_finance service code 
   # =====================================================================



from django.shortcuts import render
from django.views.decorators.http import require_GET
from .models import AgentSectionData

@require_GET
def finance_agents_modal(request):
    abn = request.GET.get("abn", "") or ""
    tx  = request.GET.get("tx", "") or ""
    saved_agents = AgentSectionData.objects.all().order_by("bot_name")

    return render(request, "finance_agents.html", {
        "abn": abn,
        "tx": tx,
        "saved_agents": saved_agents,
    })




