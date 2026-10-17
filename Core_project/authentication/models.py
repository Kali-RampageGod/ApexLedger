from django.db import models

# Create your models here.
import uuid
from django.contrib.auth.models import AbstractBaseUser,BaseUserManager,PermissionsMixin


class CustomUserManager(BaseUserManager):
    
    def create_user(self,email,password=None,**extra_fields):
        if not email:
            raise ValueError("An explicit, valid email address is mandatory for financial onboarding.")
        email=self.normalize_email(email)
        user=self.model(email=email,**extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user
    def create_superuser(self,email,password=None,**extra_fields):
        extra_fields.setdefault('is_staff',True)
        extra_fields.setdefault('is_superuser',True)
        extra_fields.setdefault('kyc_tier','TIER_3')
        return self.create_user(email,password,**extra_fields)
class User(AbstractBaseUser,PermissionsMixin):
    
        KYC_TIERS=[
        ('TIER_0', 'Unverified / Blocked'),
        ('TIER_1', 'Basic Verification - $500 Daily Limit'),
        ('TIER_2', 'Full Document Verification - $10,000 Daily Limit'),
        ('TIER_3', 'Institutional Tier - Unlimited'),
        ]
        id=models.UUIDField(primary_key=True,default=uuid.uuid4,editable=False)
        email=models.EmailField(unique=True,db_index=True)
        first_name=models.CharField(max_length=50)
        last_name=models.CharField(max_length=50)
        
        
        
        kyc_tier=models.CharField(max_length=6,choices=KYC_TIERS, default='TIER_1')
        is_frozen=models.BooleanField(default=False)
        is_active=models.BooleanField(default=True)
        is_staff=models.BooleanField(default=False)
        date_joined=models.DateTimeField(auto_now_add=True)
        
        objects=CustomUserManager()
        USERNAME_FIELD='email'
        REQUIRED_FIELDS=['first_name','last_name']
        def __str__(self):
            return f"{self.email} {self.kyc_tier}"
        
        
        
        
        