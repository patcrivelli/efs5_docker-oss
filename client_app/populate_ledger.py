import random
from datetime import timedelta, date
from django.utils import timezone

# Import Django setup
import os, django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "client_app.settings")
django.setup()

from invoice_finance.models import LedgerData   # ✅ your app name here

ABN = "13003762641"
DEBTORS = ["Woolworths", "Harris Farm Market", "Coles", "Costco", "Aldi"]

for i in range(1000):
    LedgerData.objects.create(
        abn=ABN,
        debtor=random.choice(DEBTORS),
        invoice_number=f"INV-{100000+i}",
        amount_due=random.randint(1000, 20000),
        repayment_date=date.today() + timedelta(days=random.randint(5, 120)),
        status="Open",
        created_at=timezone.now()
    )

print("✅ Inserted 1000 invoices into LedgerData")
