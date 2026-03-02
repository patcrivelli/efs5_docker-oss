


import uuid
from django.db import models

class Bank(models.Model):
    bank_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    abn = models.CharField(max_length=20, null=True, blank=True)  # ABN coming from API
    bank_name = models.CharField(max_length=255, null=True, blank=True)  # API data
    bank_slug = models.CharField(max_length=255, null=True, blank=True)  # API data
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.bank_name


class BankAccount(models.Model):
    account_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    abn = models.CharField(max_length=20, null=True, blank=True)  # ABN coming from API
    bank = models.ForeignKey(Bank, on_delete=models.CASCADE, related_name='accounts', to_field='bank_id')
    account_type = models.CharField(max_length=255, null=True, blank=True)  # API data
    account_holder = models.CharField(max_length=255, null=True, blank=True)  # API data
    account_holder_type = models.CharField(max_length=50, null=True, blank=True)  # API data
    account_name = models.CharField(max_length=255, null=True, blank=True)  # API data
    bsb = models.CharField(max_length=10, null=True, blank=True)  # API data
    account_number = models.CharField(max_length=50, null=True, blank=True)  # API data
    current_balance = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True)  # API data
    available_balance = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True)  # API data
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.account_holder} - {self.account_name}"


class Transaction(models.Model):
    transaction_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    abn = models.CharField(max_length=20, null=True, blank=True)  # ABN coming from API
    acn = models.CharField(max_length=20, null=True, blank=True)
    account = models.ForeignKey(BankAccount, on_delete=models.CASCADE, related_name='transactions', to_field='account_id')
    date = models.DateField(null=True, blank=True)  # API data
    description = models.TextField(null=True, blank=True)  # API data
    amount = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True)  # API data
    balance = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True)  # API data
    transaction_type = models.CharField(max_length=255, blank=True, null=True)  # API data
    tags = models.JSONField(null=True, blank=True)  # Store tags as a JSON object, API data
    logo = models.URLField(blank=True, null=True)  # API data
    suburb = models.CharField(max_length=255, blank=True, null=True)  # API data
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Transaction {self.transaction_id} - {self.description}"

