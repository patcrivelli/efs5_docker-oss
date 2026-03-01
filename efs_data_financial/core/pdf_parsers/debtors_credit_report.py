import os
import re
import shutil
import subprocess
import tempfile
import logging

try:
    from PyPDF2 import PdfReader
except Exception:
    PdfReader = None

try:
    from bs4 import BeautifulSoup
except Exception:
    BeautifulSoup = None

logger = logging.getLogger(__name__)

ABN_RE = re.compile(r"\bABN[:\s]+(\d{2}\s?\d{3}\s?\d{3}\s?\d{3}|\d{11})\b", re.IGNORECASE)
ACN_RE = re.compile(r"\bACN[:\s]+(\d{3}\s?\d{3}\s?\d{3}|\d{9})\b", re.IGNORECASE)

SCORE_BLOCK_RE = re.compile(
    r"\b(Risk\s*Score|RiskScore|Credit\s*Score)\b.*?(?:^|\b)([A-Z]\d)?\s*[/\-:,]*\s*(\d{2,3})\s*/\s*850",
    re.IGNORECASE | re.DOTALL,
)
A3_692_RE = re.compile(r"\b([A-Z]\d)\s*[/\-:,]*\s*(\d{2,3})\b", re.IGNORECASE)

TOTAL_ENQUIRIES_12M_RE = re.compile(
    r"(Total\s+Enquiries\s*\(.*?last\s*12\s*months.*?\)|Last\s*12\s*Months)\D+(\d{1,4})",
    re.IGNORECASE | re.DOTALL,
)

ANZSIC_HEADER_RE = re.compile(r"^\s*ANZSIC\s*Classification\s*$", re.IGNORECASE)


def _tidy_digits(s: str) -> str:
    return re.sub(r"\D", "", s or "")


def _find_first_text(regex: re.Pattern, text: str, default: str | None = None) -> str | None:
    m = regex.search(text or "")
    if not m:
        return default
    return (m.group(1) if m.lastindex else m.group(0)) or default


def _pdf_to_xml_text_lines(pdf_path: str) -> list[str]:
    if shutil.which("pdftohtml") is None:
        return []
    if BeautifulSoup is None:
        logger.warning("bs4 is not installed; cannot use XML parsing path.")
        return []

    with tempfile.NamedTemporaryFile(delete=False, suffix=".xml") as xml_tmp:
        xml_path = xml_tmp.name

    try:
        subprocess.run(
            ["pdftohtml", "-c", "-hidden", "-xml", pdf_path, xml_path],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.STDOUT,
        )
        with open(xml_path, "r", encoding="utf-8", errors="ignore") as f:
            soup = BeautifulSoup(f, "lxml-xml")

        lines: list[str] = []
        for page in soup.find_all("page"):
            for t in page.find_all("text"):
                txt = (t.get_text() or "").strip("\r\n")
                if txt:
                    lines.append(txt)
        return lines
    except Exception:
        logger.exception("pdftohtml XML parse failed")
        return []
    finally:
        try:
            os.remove(xml_path)
        except Exception:
            pass


def _pdf_to_plain_text_lines(pdf_path: str) -> list[str]:
    if PdfReader is None:
        return []
    try:
        reader = PdfReader(pdf_path)
        text = "\n".join((page.extract_text() or "") for page in reader.pages) or ""
        return [ln for ln in text.splitlines()]
    except Exception:
        logger.exception("PyPDF2 text extraction failed")
        return []


def load_pdf_lines_from_uploaded_file(django_file) -> list[str]:
    with tempfile.NamedTemporaryFile(delete=True, suffix=".pdf") as tmp:
        for chunk in django_file.chunks():
            tmp.write(chunk)
        tmp.flush()

        lines = _pdf_to_xml_text_lines(tmp.name)
        if lines:
            return lines

        return _pdf_to_plain_text_lines(tmp.name)


def extract_score(lines: list[str]) -> tuple[int | None, str | None]:
    blob = "\n".join(lines)

    m = SCORE_BLOCK_RE.search(blob)
    if m:
        band = (m.group(2) or "").strip() or None
        try:
            score = int(m.group(3))
        except Exception:
            score = None
        return score, band

    for i, ln in enumerate(lines):
        if "Very Low Risk" in ln or "RiskScore" in ln or "Credit Score" in ln:
            window = "\n".join(lines[max(0, i - 6): i + 6])
            mm = A3_692_RE.search(window)
            if mm:
                band = mm.group(1).strip().upper()
                try:
                    score = int(mm.group(2))
                except Exception:
                    score = None
                return score, band

    m2 = re.search(r"\b(\d{2,3})\s*/\s*850\b", blob)
    if m2:
        try:
            return int(m2.group(1)), None
        except Exception:
            pass

    return None, None


def extract_ids(lines: list[str]) -> tuple[str, str]:
    blob = "\n".join(lines)
    abn_raw = _find_first_text(ABN_RE, blob, "") or ""
    acn_raw = _find_first_text(ACN_RE, blob, "") or ""
    return _tidy_digits(abn_raw), _tidy_digits(acn_raw)


def extract_credit_enquiries_12m(lines: list[str]) -> int:
    blob = "\n".join(lines)
    m = TOTAL_ENQUIRIES_12M_RE.search(blob)
    if m:
        try:
            return int(m.group(2))
        except Exception:
            pass
    return 0


def extract_anzsic_descriptions(lines: list[str]) -> dict | None:
    idx = None
    for i, ln in enumerate(lines):
        if ANZSIC_HEADER_RE.match(ln.strip()):
            idx = i
            break
    if idx is None:
        return None

    collected: list[str] = []
    for ln in lines[idx + 1: idx + 10]:
        t = ln.strip()
        if not t:
            break
        if re.match(r"^(Report Generated|ASIC Extract|RiskScore|Payment Rating|Credit Enquiries|Risk Data|Registered Addresses)\b", t):
            break
        collected.append(t)

    if not collected:
        return None

    return {
        "divisionDescription": collected[0] if len(collected) >= 1 else None,
        "subdivisionDescription": collected[1] if len(collected) >= 2 else None,
        "groupDescription": collected[2] if len(collected) >= 3 else None,
        "anzsicDescription": collected[3] if len(collected) >= 4 else None,
        "divisionCode": None,
        "subdivisionCode": None,
        "groupCode": None,
        "anzsicCode": None,
    }


def _has_text(blob: str, *phrases: str) -> bool:
    blob_low = blob.lower()
    return any(p.lower() in blob_low for p in phrases)


def extract_court_judgements(lines: list[str]) -> list[dict]:
    blob = "\n".join(lines)
    if _has_text(blob, "No Court Actions"):
        return []
    return []


def extract_payment_defaults(lines: list[str]) -> list[dict]:
    blob = "\n".join(lines)
    if _has_text(blob, "No Payment Defaults Lodged"):
        return []
    return []


def extract_insolvencies(lines: list[str]) -> list[dict]:
    blob = "\n".join(lines)
    if _has_text(blob, "Bankruptcy Search Result Summary") and _has_text(blob, "No bankruptcy matches found"):
        return []
    return []


def extract_mercantile_enquiries(lines: list[str]) -> list[dict]:
    out: list[dict] = []
    date_re = re.compile(r"\b(\d{2}[-/]\d{2}[-/]\d{4})\b")
    for i, ln in enumerate(lines):
        if "Mercantile Enquiry Lodged" in ln:
            for j in range(max(0, i - 3), i + 1):
                m = date_re.search(lines[j])
                if m:
                    out.append({
                        "enquiryDate": m.group(1),
                        "status": "Mercantile Enquiry Lodged",
                        "agent": None,
                    })
                    break
    return out


def build_report_json(abn: str, acn: str, score_val: int | None, lines: list[str]) -> tuple[dict, int]:
    anzsic = extract_anzsic_descriptions(lines)
    credit_enquiries_12m = extract_credit_enquiries_12m(lines)

    report = {
        "summary": {
            "abn": abn or "",
            "acn": acn or "",
            "score": {"band": None, "value": score_val, "outOf": 850},
            "creditEnquiries": credit_enquiries_12m,
        },
        "anzsic": anzsic,
        "loans": [],
        "insolvencies": extract_insolvencies(lines),
        "courtJudgements": extract_court_judgements(lines),
        "paymentDefaults": extract_payment_defaults(lines),
        "mercantileEnquiries": extract_mercantile_enquiries(lines),
    }
    return report, int(credit_enquiries_12m or 0)
