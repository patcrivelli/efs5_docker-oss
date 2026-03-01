# efs_apis/core/services.py
import re
import requests
from typing import Any, Dict, Optional
from django.conf import settings

REQUESTS_DEFAULT_TIMEOUT = getattr(settings, "REQUESTS_DEFAULT_TIMEOUT", 12)
EFS_DATA_BUREAU_BASE_URL = getattr(settings, "EFS_DATA_BUREAU_BASE_URL", "http://localhost:8018").rstrip("/")

# 🔒 Hardcoded CreditorWatch application token (testing only!)
# efs_apis/core/services.py

# 🔒 Hardcoded CreditorWatch application token (for testing only!)
APPLICATION_BUREAU_TOKEN = (
    "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9."
    "eyJzdWIiOiIxMjM0NTY3ODkwIiwibmFtZSI6IkNyZWRpdG9yd2F0Y2giLCJpYXQiOjE1MTYyMzkwMjIs"
    "InRoYW5rcyI6IlRoYW5rcyBmb3IgdHJ5aW5nIG91dCB0aGUgQ1cgQVBJLCB3ZSdkIGxvdmUgdG8gaGF2"
    "ZSB5b3UgYXMgYSBjdXN0b21lciA6KSJ9."
    "q5hTaEcKnCKF9MV1jYu9UJrHANexixRApb3IpG9AyHc"
)


class ServiceError(RuntimeError):
    pass

def _normalize_bearer_token(raw: str) -> str:
    if not raw:
        return ""
    t = raw.strip()
    if t.lower().startswith("bearer "):
        t = t[7:].lstrip()
    t = (t
         .replace("\u2014", "-")
         .replace("\u2013", "-")
         .replace("\u2212", "-"))
    t = t.strip('\'"')
    t = re.sub(r"[\u200B-\u200D\uFEFF]", "", t)
    t = re.sub(r"[^\x20-\x7E]", "", t)
    return t
class CreditorWatchClient:
    def __init__(self, token: Optional[str] = None, timeout: Optional[int] = None) -> None:
        # Always use the hardcoded token for testing
        self.token = APPLICATION_BUREAU_TOKEN
        self.timeout = timeout or REQUESTS_DEFAULT_TIMEOUT

    def _headers(self) -> Dict[str, str]:
        return {"Authorization": f"Bearer {self.token}"}

    def get_credit_report(self, abn: str, acn: Optional[str] = None) -> Dict[str, Any]:
        url = "https://api-sandbox.creditorwatch.com.au/credit-report"
        params = {
            "abn": abn,
            "ato-tax-default": "true",
            "lenders": "true",
            "anzsic": "true",
        }
        if acn:
            params["acn"] = acn
        r = requests.get(url, headers=self._headers(), params=params, timeout=self.timeout)
        if not r.ok:
            raise ServiceError(f"CreditorWatch credit-report {r.status_code}: {r.text[:200]}")
        return r.json()

    def get_credit_score(self, abn: str, acn: Optional[str] = None) -> Dict[str, Any]:
        url = "https://api-sandbox.creditorwatch.com.au/credit-score"
        params = {"abn": abn}
        if acn:
            params["acn"] = acn
        r = requests.get(url, headers=self._headers(), params=params, timeout=self.timeout)
        if not r.ok:
            raise ServiceError(f"CreditorWatch credit-score {r.status_code}: {r.text[:200]}")
        return r.json()


class BureauDataServiceClient:
    def __init__(self, timeout: Optional[int] = None) -> None:
        self.timeout = timeout or REQUESTS_DEFAULT_TIMEOUT

    def store_credit_bundle(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        url = f"{EFS_DATA_BUREAU_BASE_URL}/api/bureau/store-credit-report-data/"
        r = requests.post(url, json=payload, timeout=self.timeout)
        try:
            body = r.json()
        except ValueError:
            body = {"raw": r.text[:300]}
        if not r.ok:
            raise ServiceError(f"efs_data_bureau store {r.status_code}: {str(body)[:200]}")
        return body

# efs_apis/core/services.py
import re
import requests
from typing import Any, Dict, Optional
from django.conf import settings

REQUESTS_DEFAULT_TIMEOUT = getattr(settings, "REQUESTS_DEFAULT_TIMEOUT", 12)

# Internal service bases (no envs; set in settings.py)
EFS_DATA_FINANCIAL_BASE_URL = getattr(settings, "EFS_DATA_FINANCIAL_BASE_URL", "http://localhost:8019").rstrip("/")
EFS_INTERNAL_API_KEY        = getattr(settings, "INTERNAL_API_KEY", "dev-key")

# CreditorWatch config
EFS_CW_BASE       = getattr(settings, "EFS_CW_BASE", "https://api-sandbox.creditorwatch.com.au").rstrip("/")
EFS_CW_APP_TOKEN  = getattr(settings, "EFS_CW_APP_TOKEN", "").strip()  # <-- put your JWT here (without "Bearer ")

class ServiceError(RuntimeError):
    """Generic service error for upstream or internal calls."""


def _normalize_bearer_token(raw: str) -> str:
    """Strip 'Bearer ' prefix, quotes, zero-width, exotic dashes, and non-ascii."""
    if not raw:
        return ""
    t = raw.strip()
    if t.lower().startswith("bearer "):
        t = t[7:].lstrip()
    t = (
        t.replace("\u2014", "-")  # em dash —
         .replace("\u2013", "-")  # en dash –
         .replace("\u2212", "-")  # minus sign −
    )
    t = t.strip('\'"')
    t = re.sub(r"[\u200B-\u200D\uFEFF]", "", t)  # zero-width
    t = re.sub(r"[^\x20-\x7E]", "", t)          # ASCII visible only
    return t


class CreditorWatchClient:
    """
    Thin HTTP client for CreditorWatch Sandbox.
    Reads default token from settings, but you can pass a token per-call.
    """
    def __init__(self, token: Optional[str] = None, timeout: Optional[int] = None) -> None:
        raw = token or EFS_CW_APP_TOKEN
        self.token = _normalize_bearer_token(raw)
        self.timeout = timeout or REQUESTS_DEFAULT_TIMEOUT

    def _headers(self) -> Dict[str, str]:
        if not self.token:
            raise ServiceError("CreditorWatch token is empty; set EFS_CW_APP_TOKEN in settings.py")
        return {"Authorization": f"Bearer {self.token}"}

    def get_credit_report(self, abn: str, acn: Optional[str] = None) -> Dict[str, Any]:
        url = f"{EFS_CW_BASE}/credit-report"
        params = {
            "abn": abn,
            "ato-tax-default": "true",
            "lenders": "true",
            "anzsic": "true",
        }
        if acn:
            params["acn"] = acn
        r = requests.get(url, headers=self._headers(), params=params, timeout=self.timeout)
        if not r.ok:
            raise ServiceError(f"CreditorWatch credit-report {r.status_code}: {r.text[:200]}")
        return r.json()

    def get_credit_score(self, abn: str, acn: Optional[str] = None) -> Dict[str, Any]:
        url = f"{EFS_CW_BASE}/credit-score"
        params = {"abn": abn}
        if acn:
            params["acn"] = acn
        r = requests.get(url, headers=self._headers(), params=params, timeout=self.timeout)
        if not r.ok:
            raise ServiceError(f"CreditorWatch credit-score {r.status_code}: {r.text[:200]}")
        return r.json()

    def get_financials(self, abn: str, year: Optional[int] = None) -> Dict[str, Any]:
        """
        GET {BASE}/financials/{abn}[?year=YYYY]
        """
        url = f"{EFS_CW_BASE}/financials/{abn}"
        params = {}
        if year:
            params["year"] = str(year)
        r = requests.get(url, headers=self._headers(), params=params, timeout=self.timeout)
        if not r.ok:
            raise ServiceError(f"CreditorWatch financials {r.status_code}: {r.text[:200]}")
        return r.json()


class FinancialDataServiceClient:
    """
    Client for efs_data_financial service (port 8019 by default).
    """
    def __init__(self, timeout: Optional[int] = None) -> None:
        self.timeout = timeout or REQUESTS_DEFAULT_TIMEOUT

    def store_financials(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        POST to efs_data_financial to persist. Accepts either:
          { record: {...} }  OR  { records: [ {...}, {...} ] }
        """
        url = f"{EFS_DATA_FINANCIAL_BASE_URL}/api/financials/store/"
        headers = {"X-API-Key": EFS_INTERNAL_API_KEY, "Content-Type": "application/json"}
        r = requests.post(url, json=payload, headers=headers, timeout=self.timeout)
        try:
            body = r.json()
        except ValueError:
            body = {"raw": r.text[:300]}
        if not r.ok:
            raise ServiceError(f"efs_data_financial store {r.status_code}: {str(body)[:200]}")
        return body
