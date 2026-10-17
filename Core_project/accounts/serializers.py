import random
from decimal import Decimal
from rest_framework import serializers
from django.db import transaction
from .models import AssetAccount, LedgerTransaction

# 🧰 TOOL 1: For viewing account lists and creating secondary wallets (Savings/Reserve)
class AssetAccountSerializer(serializers.ModelSerializer):
    """
    Handles viewing account details and provisioning secondary pockets.
    """
    balance = serializers.DecimalField(max_digits=18, decimal_places=2, read_only=True)
    account_number = serializers.CharField(read_only=True)

    class Meta:
        model = AssetAccount
        fields = ['id', 'account_number', 'account_type', 'currency', 'balance', 'created_at']
        read_only_fields = ['id', 'created_at']

    def validate_account_type(self, value):
        """
        Safety Check: Ensure a user doesn't try to open multiple PRIMARY checking accounts.
        """
        user = self.context['request'].user
        if value == 'PRIMARY' and AssetAccount.objects.filter(user=user, account_type='PRIMARY').exists():
            raise serializers.ValidationError("You already possess an active primary checking account allocation.")
        return value

    def create(self, validated_data):
        """
        Triggers when an existing user opens an extra pocket from their dashboard.
        """
        validated_data['user'] = self.context['request'].user
        
        def generate_number():
            return "".join([str(random.randint(0, 9)) for _ in range(16)])
            
        account_num = generate_number()
        while AssetAccount.objects.filter(account_number=account_num).exists():
            account_num = generate_number()
            
        validated_data['account_number'] = account_num
        return super().create(validated_data)


# 🧰 TOOL 2: For executing secure, thread-safe money transfers between accounts
class TransferFundsSerializer(serializers.ModelSerializer):
    """
    Validates and executes a thread-safe, double-entry asset transfer.
    """
    source_account_number = serializers.CharField(write_only=True)
    destination_account_number = serializers.CharField(write_only=True)

    class Meta:
        model = LedgerTransaction
        fields = ['source_account_number', 'destination_account_number', 'amount', 'description']

    def validate(self, data):
        user = self.context['request'].user
        
        # 1. Look up the accounts
        try:
            source_acc = AssetAccount.objects.get(account_number=data['source_account_number'], user=user, is_active=True)
        except AssetAccount.DoesNotExist:
            raise serializers.ValidationError({"source_account_number": "Source account not found or access denied."})

        try:
            destination_acc = AssetAccount.objects.get(account_number=data['destination_account_number'], is_active=True)
        except AssetAccount.DoesNotExist:
            raise serializers.ValidationError({"destination_account_number": "Destination bank account number does not exist."})

        # 2. Prevent self-transfers
        if source_acc == destination_acc:
            raise serializers.ValidationError("Cannot execute a transfer where source and destination are identical.")

        # 3. Prevent negative or zero transfers
        if data['amount'] <= Decimal('0.00'):
            raise serializers.ValidationError({"amount": "Transfer value must be greater than zero."})

        # 4. Check funds availability
        if source_acc.balance < data['amount']:
            raise serializers.ValidationError({"amount": "Inadequate liquidity allocation to clear this transfer operation."})

        self.context['source_acc'] = source_acc
        self.context['destination_acc'] = destination_acc
        return data

    def create(self, validated_data):
        amount = validated_data['amount']
        description = validated_data.get('description', '')

        # THE MUTEX LOCK SEQUENCE
        with transaction.atomic():
            source_query = AssetAccount.objects.select_for_update().filter(id=self.context['source_acc'].id)
            dest_query = AssetAccount.objects.select_for_update().filter(id=self.context['destination_acc'].id)
            
            source_lock = source_query.first()
            dest_lock = dest_query.first()

            if source_lock.balance < amount:
                raise serializers.ValidationError("Transaction aborted: Funds depleted by a concurrent thread request.")

            tx = LedgerTransaction.objects.create(
                tx_type='TRANSFER',
                source_account=source_lock,
                destination_account=dest_lock,
                amount=amount,
                description=description
            )
            
        return tx