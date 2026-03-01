import os
import requests

def efs_nav_context(request):
    services = {
        "client":        os.getenv("EFS_CLIENT_URL",       "http://localhost:8000"),
        "sales":         os.getenv("EFS_SALES_URL",        "http://localhost:8001"),
        "profile":       os.getenv("EFS_PROFILE_URL",      "http://localhost:8002"),
        "data":          os.getenv("EFS_DATA_URL",         "http://localhost:8003"),
        "operations":    os.getenv("EFS_OPERATIONS_URL",   "http://localhost:8004"),
        "risk":          os.getenv("EFS_RISK_URL",         "http://localhost:8005"),
        "finance":       os.getenv("EFS_FINANCE_URL",      "http://localhost:8006"),
        "drawdowns":     os.getenv("EFS_DRAWDOWNS_URL",    "http://localhost:8007"),
        "lms":           os.getenv("EFS_LMS_URL",          "http://localhost:8008"),
        "collections":   os.getenv("EFS_COLLECTIONS_URL",  "http://localhost:8009"),
        "notifications": os.getenv("EFS_NOTIFICATIONS_URL","http://localhost:8010"),
        "liquidity":     os.getenv("EFS_LIQUIDITY_URL",    "http://localhost:8011"),
        "pnl":           os.getenv("EFS_PNL_URL",          "http://localhost:8012"),
        "settings":      os.getenv("EFS_SETTINGS_URL",     "http://localhost:8013"),
        "applications":  os.getenv("EFS_APPLICATIONS_URL", "http://localhost:8014"),
        "agents":        os.getenv("EFS_AGENTS_URL",       "http://localhost:8015"),
        "application_aggregate": os.getenv("EFS_APPLICATION_AGGREGATE_URL", "http://localhost:8016"),
        "apis":                  os.getenv("EFS_APIS_URL",                  "http://localhost:8017"),
        "data_bureau":           os.getenv("EFS_DATA_BUREAU_URL",          "http://localhost:8018"),
        "data_financial":        os.getenv("EFS_DATA_FINANCIAL_URL",       "http://localhost:8019"),
        "data_bankstatements":   os.getenv("EFS_DATA_BANKSTATEMENTS_URL",  "http://localhost:8020"),
        "crosssell":             os.getenv("EFS_CROSSELL_URL",             "http://localhost:8021"),
        "credit_decision":       os.getenv("EFS_CREDIT_DECISION_URL",      "http://localhost:8022"),

        # LMS split
        "lms_asset_finance":   os.getenv("EFS_LMS_ASSET_FINANCE_URL",   "http://localhost:8023"),
        "lms_invoice_finance": os.getenv("EFS_LMS_INVOICE_FINANCE_URL", "http://localhost:8024"),
        "lms_overdraft":       os.getenv("EFS_LMS_OVERDRAFT_URL",       "http://localhost:8025"),
        "lms_scf":             os.getenv("EFS_LMS_SCF_URL",             "http://localhost:8026"),
        "lms_term_loan":       os.getenv("EFS_LMS_TERM_LOAN_URL",       "http://localhost:8027"),
        "lms_trade_finance":   os.getenv("EFS_LMS_TRADE_FINANCE_URL",   "http://localhost:8028"),

        # RAG services (each has its own port)
        "ingestion":  os.getenv("EFS_RAG_INGESTION_URL",  "http://localhost:8029"),
        "chunking":   os.getenv("EFS_RAG_CHUNKING_URL",   "http://localhost:8030"),
        "embeddings": os.getenv("EFS_RAG_EMBEDDINGS_URL", "http://localhost:8031"),
        "retrieval":  os.getenv("EFS_RAG_RETRIEVAL_URL",  "http://localhost:8032"),
        "generation": os.getenv("EFS_RAG_GENERATION_URL", "http://localhost:8033"),
        "evaluation": os.getenv("EFS_RAG_EVALUATION_URL", "http://localhost:8034"),
    }

    return {"EFS_SERVICES": services}



#-------------#-------------#-------------#-------------


#left sidebar application data fetch 


#-------------#-------------#-------------#-------------



def originators_context(request):
    import logging
    logger = logging.getLogger(__name__)

    base = os.getenv("EFS_PROFILE_URL", "http://localhost:8002")
    api_url = f"{base.rstrip('/')}/api/originators/"

    originators = []
    selected_originator = None
    originator_id = request.GET.get("originators")

    try:
        resp = requests.get(api_url, timeout=5)
        logger.warning(f"🔎 Originator API {api_url} returned {resp.status_code}")
        if resp.status_code == 200:
            data = resp.json()
            if isinstance(data, list):
                originators = data
                logger.warning(f"✅ Got originators: {originators}")
    except Exception as e:
        logger.error(f"❌ Originator API error: {e}")

    # normalize selection
    if originator_id and originators:
        for org in originators:
            if str(org.get("id")) == str(originator_id):
                selected_originator = {"id": org.get("id"), "originator": org.get("originator")}
                break

    return {
        "originators": originators,
        "selected_originator": selected_originator,
    }


#-------------#-------------#-------------#-------------


#right sidebar application data fetch 


#-------------#-------------#-------------#-------------



import os
import requests
import logging

logger = logging.getLogger(__name__)

def live_deals_context(request):
    """
    Adds `live_deals` to template context for right sidebar dropdown.
    Fetches from application_aggregate service.
    """
    # Use your existing service map env var
    base = os.getenv("EFS_APPLICATION_AGGREGATE_URL", "http://localhost:8016")

    # Pick the correct API path in your aggregate service:
    # Example: /api/live-deals/
    api_url = f"{base.rstrip('/')}/api/live-deals/"

    # preserve originator filtering if you want:
    originator_id = request.GET.get("originators")

    params = {}
    if originator_id:
        params["originators"] = originator_id

    try:
        resp = requests.get(api_url, params=params, timeout=5)
        logger.warning(f"🔎 Live deals API {resp.url} returned {resp.status_code}")

        if resp.status_code == 200:
            data = resp.json()

            # accept either {"results":[...]} or {"live_deals":[...]} or direct list
            if isinstance(data, list):
                deals = data
            elif isinstance(data, dict):
                deals = data.get("live_deals") or data.get("results") or []
            else:
                deals = []

            return {"live_deals": deals}

    except Exception as e:
        logger.exception(f"❌ Live deals API error: {e}")

    return {"live_deals": []}
