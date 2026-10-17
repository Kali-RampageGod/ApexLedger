import random
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.contrib.auth import get_user_model
from .models import AssetAccount

User = get_user_model()

def generate_unique_account_number():
    """Generates a random, string-safe 16-digit account number."""
    return "".join([str(random.randint(0, 9)) for _ in range(16)])

@receiver(post_save, sender=User)
def create_customer_checking_account(sender, instance, created, **kwargs):
    """
    Automated Account Generator Tripwire.
    Runs every single time a User row is committed to the database.
    """
    if created:  # Enforces that this only triggers on NEW signups, not updates
        account_num = generate_unique_account_number()
        
        # Guard Loop: In the extreme event of a collision, keep rolling numbers
        while AssetAccount.objects.filter(account_number=account_num).exists():
            account_num = generate_unique_account_number()
            
        # Write the bank account pocket to the ledger database
        AssetAccount.objects.create(
            user=instance,
            account_number=account_num,
            account_type='PRIMARY',
            currency='INR'
        )