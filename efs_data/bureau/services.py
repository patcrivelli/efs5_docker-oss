# efs_data/bureau/services.py
import logging
from django.db import transaction
from datetime import datetime
from .models import (
    CreditScore, CreditScoreHistory,
    CreditReport, CompanySearch, DataBlock
)
from .serializers import (
    CreditScoreSerializer, CreditScoreHistorySerializer,
    CreditReportSerializer, CompanySearchSerializer, DataBlockSerializer
)

logger = logging.getLogger(__name__)

# -------------------------------
# 🔹 Store Credit Report + Scores
# -------------------------------
class StoreCreditReportService:

    @staticmethod
    @transaction.atomic
    def store_data(data):
        try:
            abn = data.get("abn")
            if not abn:
                return False, "ABN missing from payload"

            # --- Credit Report ---
            credit_report_data = data.get("credit_report", {}).get("creditReport", {})
            if credit_report_data:
                serializer = CreditReportSerializer(data={
                    "abn": abn,
                    "description": credit_report_data.get("description", ""),
                    "item_code": credit_report_data.get("itemCode", ""),
                    "credit_enquiries": credit_report_data.get("creditEnquiries", 0),
                    "report": credit_report_data.get("report", {}),
                    "acn": credit_report_data.get("acn", ""),
                })
                if serializer.is_valid():
                    serializer.save()
                else:
                    return False, f"CreditReport validation failed: {serializer.errors}"

            # --- Credit Score ---
            credit_score_data = data.get("credit_score", {}).get("creditScore", {})
            if credit_score_data:
                CreditScore.objects.create(
                    abn=abn,
                    current_credit_score=credit_score_data.get("scores", {}).get("currentCreditScore"),
                    description=credit_score_data.get("description", ""),
                    item_code=credit_score_data.get("itemCode", "")
                )

                # --- Credit Score History ---
                for h in credit_score_data.get("scores", {}).get("creditScoreHistory", []):
                    hist_serializer = CreditScoreHistorySerializer(data={
                        "abn": abn,
                        "date": datetime.strptime(h["date"], "%d-%m-%Y").date(),
                        "score": h["score"]
                    })
                    if hist_serializer.is_valid():
                        hist_serializer.save()
                    else:
                        return False, f"CreditScoreHistory validation failed: {hist_serializer.errors}"

            return True, "Credit report + scores stored successfully"

        except Exception as e:
            logger.exception("Error storing bureau data in StoreCreditReportService")
            return False, str(e)


# -------------------------------
# 🔹 Store Company Search (updated)
# -------------------------------
class StoreCompanySearchService:
    @staticmethod
    @transaction.atomic
    def store_company_search_data(acn, company_json):
        try:
            serializer = CompanySearchSerializer(data={
                "page": company_json.get("page"),
                "results_per_page": company_json.get("resultsPerPage"),
                "count": company_json.get("count"),
                "number_of_pages": company_json.get("numberOfPages"),
                "results": company_json.get("results", []),
            })
            if serializer.is_valid():
                serializer.save()
                return True, "Company data stored"
            return False, serializer.errors
        except Exception as e:
            logger.exception("Error in StoreCompanySearchService")
            return False, str(e)


# -------------------------------
# 🔹 Store DataBlock (already good)
# -------------------------------
class StoreDataBlockService:
    @staticmethod
    @transaction.atomic
    def store_data_block_data(abn, datablock_json):
        try:
            logger.info(f"Storing DataBlock for {abn}, keys={list(datablock_json.keys())}")
            serializer = DataBlockSerializer(data={**datablock_json, "abn": abn})
            if serializer.is_valid():
                serializer.save()
                return True, "Datablock stored"
            else:
                logger.error(f"Validation failed: {serializer.errors}")
                return False, serializer.errors
        except Exception as e:
            logger.exception("Error in StoreDataBlockService")
            return False, str(e)
