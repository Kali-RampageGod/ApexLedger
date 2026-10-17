import uuid
from django.db import models
from django.conf import settings
from decimal import Decimal

class AssetAccount(models.Model):
    """
    Represents an individual liquidity asset pocket for a user.
    A single user can hold multiple accounts (e.g., Primary, Savings).
    """
    ACCOUNT_TYPES = [
        ('PRIMARY', 'Primary Checking'),
        ('SAVINGS', 'Savings Yield Account'),
        ('RESERVE', 'Escrow Operational Hold'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='accounts')
    account_number = models.CharField(max_length=16, unique=True, db_index=True)
    account_type = models.CharField(max_length=10, choices=ACCOUNT_TYPES, default='PRIMARY')
    currency = models.CharField(max_length=3, default='INR')
    created_at = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(default=True)

    @property
    def balance(self):
        """
        Dynamically calculates the absolute net balance by tracing the transaction history.
        In double-entry: Net Balance = (Sum of Credits) - (Sum of Debits)
        """
        credits = self.credit_entries.aggregate(total=models.Sum('amount'))['total'] or Decimal('0.00')
        debits = self.debit_entries.aggregate(total=models.Sum('amount'))['total'] or Decimal('0.00')
        return credits - debits

    def __str__(self):
        return f"{self.account_number} ({self.user.email})"


class LedgerTransaction(models.Model):
    """
    An unchangeable, single audit ledger record tracking a physical 
    movement of money between two AssetAccounts.
    """
    TRANSACTION_TYPES = [
        ('TRANSFER', 'Internal P2P Transfer'),
        ('DEPOSIT', 'Fiat Inbound Liquidity'),
        ('WITHDRAW', 'External Gateway Outbound'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tx_type = models.CharField(max_length=10, choices=TRANSACTION_TYPES, default='TRANSFER')
    
    # Double-Entry Linking Legs
    source_account = models.ForeignKey(
        AssetAccount, 
        on_delete=models.PROTECT, 
        related_name='debit_entries', 
        null=True, blank=True  # Null only for initial external bank deposits
    )
    destination_account = models.ForeignKey(
        AssetAccount, 
        on_delete=models.PROTECT, 
        related_name='credit_entries',
        null=True, blank=True  # Null only for full outbound external withdrawals
    )
    
    # Financial precision parameters
    amount = models.DecimalField(max_length=20, max_digits=18, decimal_places=2)
    description = models.CharField(max_length=255, blank=True)
    timestamp = models.DateTimeField(auto_now_add=True, db_index=True)

    def __str__(self):
        return f"TX: {self.id} | {self.amount} {self.source_account} -> {self.destination_account}"
   
# Create your models here.
