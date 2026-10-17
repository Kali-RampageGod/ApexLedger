import random  # 🌟 Added: To generate the random 16 digits
from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from django.contrib.auth import get_user_model
from django.db import transaction  # 🌟 Added: To make the registration atomic

# 🌟 Added: Import the AssetAccount model from your accounts app
from accounts.models import AssetAccount

User = get_user_model()

class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    @classmethod
    def get_token(cls, user):
        token = super().get_token(cls.user if hasattr(cls, 'user') else user)
        token['email'] = user.email
        token['kyc_tier'] = user.kyc_tier
        token['is_frozen'] = user.is_frozen
        return token

class UserRegistrationSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, min_length=8)
    
    # 🌟 Added: Accept an optional account type (defaults to 'PRIMARY' if they leave it out)
    account_type = serializers.ChoiceField(
        choices=AssetAccount.ACCOUNT_TYPES, 
        default='PRIMARY', 
        write_only=True
    )

    class Meta:
        model = User
        # 🌟 Added: Include 'account_type' in your fields list
        fields = ['email', 'password', 'first_name', 'last_name', 'account_type']

    def create(self, validated_data):
        # 🌟 Changed: Pull out the account type so it doesn't break User creation
        account_type = validated_data.pop('account_type', 'PRIMARY')

        # 🌟 Changed: Wrap everything in a transaction block for safety
        with transaction.atomic():
            # 1. Create the base User profile securely
            user = User.objects.create_user(**validated_data)

            # 2. Generate a unique 16-digit account number sequence
            def generate_number():
                return "".join([str(random.randint(0, 9)) for _ in range(16)])
            
            account_num = generate_number()
            # Safety check: loop until we find a completely unused number
            while AssetAccount.objects.filter(account_number=account_num).exists():
                account_num = generate_number()

            # 3. Mint the bank account row instantly
            AssetAccount.objects.create(
                user=user,
                account_number=account_num,
                account_type=account_type,
                currency='INR'
            )

        return user