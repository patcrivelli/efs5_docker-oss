# financial/services.py
import logging
from django.db import transaction
from dateutil import parser
from .models import InvoiceData, LedgerData, FinancialData, Registration
from .serializers import (
    InvoiceDataSerializer,
    LedgerDataSerializer,
    RegistrationSerializer,
)

logger = logging.getLogger(__name__)


class LoanApplicationService:
    """Handles invoice + ledger ingestion."""

    @staticmethod
    def process_invoice_data(data):
        invoices = data.get("invoices", [])
        if not invoices:
            return {"status": "error", "message": "No invoices found"}

        unique_invoices, skipped = [], []

        for invoice in invoices:
            abn = invoice.get("abn")
            inv_number = invoice.get("inv_number")
            if abn and inv_number:
                if not InvoiceData.objects.filter(abn=abn, inv_number=inv_number).exists():
                    unique_invoices.append(invoice)
                else:
                    skipped.append(inv_number)

        if not unique_invoices:
            return {"status": "skipped", "message": f"All invoices were duplicates: {skipped}"}

        serializer = InvoiceDataSerializer(data=unique_invoices, many=True)
        if serializer.is_valid():
            serializer.save()
            return {
                "status": "success",
                "message": f"{len(unique_invoices)} invoices saved. Skipped {len(skipped)} duplicates.",
                "skipped": skipped,
            }
        return {"status": "error", "message": serializer.errors}

    @staticmethod
    def process_ledger_data(data):
        unique_ledgers, skipped = [], []

        for entry in data:
            abn = entry.get("abn")
            invoice_number = entry.get("invoice_number")
            if abn and invoice_number:
                if not LedgerData.objects.filter(abn=abn, invoice_number=invoice_number).exists():
                    unique_ledgers.append(entry)
                else:
                    skipped.append(invoice_number)

        if not unique_ledgers:
            return {"status": "skipped", "message": f"All ledger entries were duplicates: {skipped}"}

        serializer = LedgerDataSerializer(data=unique_ledgers, many=True)
        if serializer.is_valid():
            serializer.save()
            return {
                "status": "success",
                "message": f"{len(unique_ledgers)} ledger entries saved. Skipped {len(skipped)} duplicates.",
                "skipped": skipped,
            }
        return {"status": "error", "message": serializer.errors}


class StoreFinancialDataService:
    """Handles company-level financial statements."""

    @staticmethod
    def store_financial_data(data):
        try:
            company = data.get("company", {})
            financials = data.get("financials", [])

            for financial in financials:
                financial_year = financial.get("financialYear")
                profit_and_loss = financial.get("financialStatement", {}).get("profitAndLoss", {})
                balance_sheet = financial.get("financialStatement", {}).get("balanceSheet", {})

                FinancialData.objects.update_or_create(
                    abn=company.get("abn", ""),
                    year=financial_year,
                    defaults={
                        "company_name": company.get("name", ""),
                        "financials": financial,
                        "profit_loss": profit_and_loss,
                        "balance_sheet": balance_sheet,
                        "raw": financial,
                    },
                )
                logger.info(
                    f"Financial data for ABN {company.get('abn')} and year {financial_year} stored successfully."
                )

        except Exception as e:
            logger.error(f"Error while storing financial data: {e}")
            raise




from django.db import transaction
from dateutil import parser
import logging
from .serializers import RegistrationSerializer

logger = logging.getLogger(__name__)

class StorePPSRDataService:
    """Handles PPSR registrations ingestion."""

    @staticmethod
    @transaction.atomic
    def store_ppsr_data(ppsr_data, abn, acn=None):
        """
        Processes and stores PPSR registration data into Registration model.
        """
        registrations = ppsr_data.get("registrations", [])
        search_date_str = ppsr_data.get("searchDate")

        if not registrations:
            logger.warning(f"No registrations found in PPSR data for ABN {abn}")
            # Still log the search event (optional: create a placeholder Registration record)
            return True, "No registrations found but search logged successfully."

        for registration in registrations:
            registration_data = {
                "abn": abn,
                "search_date": StorePPSRDataService.parse_date(search_date_str),
                "registration_number": registration.get("registrationNumber"),
                "start_time": StorePPSRDataService.parse_datetime(registration.get("startTime")),
                "end_time": StorePPSRDataService.parse_datetime(registration.get("endTime")),
                "change_number": registration.get("changeNumber"),
                "change_time": StorePPSRDataService.parse_datetime(registration.get("changeTime")),
                "registration_kind": registration.get("registrationKind"),
                "is_migrated": registration.get("isMigrated"),
                "is_transitional": registration.get("isTransitional"),
                "grantor_organisation_identifier": registration.get("grantorOrganisationIdentifier"),
                "grantor_organisation_identifier_type": registration.get("grantorOrganisationIdentifierType"),
                "grantor_organisation_name": registration.get("grantorOrganisationName"),
                "collateral_class_type": registration.get("collateralClassType"),
                "collateral_type": registration.get("collateralType"),
                "collateral_class_description": registration.get("collateralClassDescription"),
                "are_proceeds_claimed": registration.get("areProceedsClaimed"),
                "proceeds_claimed_description": registration.get("proceedsClaimedDescription"),
                "is_security_interest_registration_kind": registration.get("isSecurityInterestRegistrationKind"),
                "are_assets_subject_to_control": registration.get("areAssetsSubjectToControl"),
                "is_inventory": registration.get("isInventory"),
                "is_pmsi": registration.get("isPmsi"),
                "is_subordinate": registration.get("isSubordinate"),
                "giving_of_notice_identifier": registration.get("givingOfNoticeIdentifier"),
                "security_party_groups": registration.get("securityPartyGroups", []),
                "grantors": registration.get("grantors", []),
                "address_for_service": registration.get("addressForService", {}),
            }

            serializer = RegistrationSerializer(data=registration_data)
            if serializer.is_valid():
                serializer.save()
                logger.info(f"✅ Saved PPSR registration {registration_data['registration_number']}")
            else:
                logger.error(f"❌ Validation failed for PPSR registration: {serializer.errors}")
                return False, {"error": "Validation failed", "details": serializer.errors}

        return True, "All PPSR registrations stored successfully"

    @staticmethod
    def parse_datetime(datetime_str):
        if datetime_str:
            try:
                return parser.isoparse(datetime_str)
            except Exception as e:
                logger.warning(f"Could not parse datetime '{datetime_str}': {e}")
        return None

    @staticmethod
    def parse_date(date_str):
        if date_str:
            try:
                return parser.isoparse(date_str).date()
            except Exception as e:
                logger.warning(f"Could not parse date '{date_str}': {e}")
        return None



import logging
from .models import FinancialData

logger = logging.getLogger(__name__)

class StoreFinancialDataService:
    @staticmethod
    def store_financial_data(data):
        try:
            # Fetch the company and financials data from the API response
            company = data.get('company', {})
            financials = data.get('financials', [])

            # Loop through each financial year data to store it
            for financial in financials:
                financial_year = financial.get('financialYear')
                profit_and_loss = financial.get('financialStatement', {}).get('profitAndLoss', {})
                balance_sheet = financial.get('financialStatement', {}).get('balanceSheet', {})

                # Create or update the FinancialData instance
                FinancialData.objects.update_or_create(
                    abn=company.get('abn', ''),
                    year=financial_year,
                    defaults={
                        'company_name': company.get('name', ''),
                        'financials': financial,
                        'profit_loss': profit_and_loss,
                        'balance_sheet': balance_sheet,
                        'raw': financial  # Store the raw financial data as JSON
                    }
                )
                
                logger.info(f"Financial data for ABN {company.get('abn')} and year {financial_year} stored successfully.")

        except KeyError as e:
            logger.error(f"KeyError while storing financial data: {e}")
            raise
        except Exception as e:
            logger.error(f"An error occurred while storing financial data: {e}")
            raise