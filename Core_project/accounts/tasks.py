import time
from celery import shared_task
from django.core.mail import send_mail
from .models import LedgerTransaction

@shared_task
def send_transaction_email_task(transaction_id):
    """
    Asynchronous Background Worker Engine.
    Triggered by Redis, executed by Celery.
    """
    try:
        # Fetch the transaction historical context row
        tx = LedgerTransaction.objects.get(id=transaction_id)
        
        # Simulate network latency or heavy crypto receipt generation
        # (This represents the 2-3 second delay connecting to an email server)
        time.sleep(3)

        # Inbound and Outbound notification generation logic
        subject = f"Fintech Transaction Alert: {tx.tx_type}"
        message = (
            f"A ledger movement occurred.\n\n"
            f"Transaction Hash: {tx.id}\n"
            f"Quantum Value: {tx.amount} INR\n"
            f"Timestamp Vector: {tx.timestamp}\n"
        )
        
        # Fire email to the account owner (Source account user)
        if tx.source_account and tx.source_account.user.email:
            send_mail(
                subject=subject,
                message=message + f"Action: Funds Debited from your pocket.",
                from_email="ledger-alerts@fintech.local",
                recipient_list=[tx.source_account.user.email],
                fail_silently=False,
            )
            
        return f"Successfully processed notification loop for TX {transaction_id}"
        
    except LedgerTransaction.DoesNotExist:
        return f"Aborted: Transaction record {transaction_id} not committed to disk yet."