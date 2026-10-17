from rest_framework import generics, status
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from .models import AssetAccount
from .serializers import AssetAccountSerializer, TransferFundsSerializer
from authentication.authenticate import CustomCookieJWTAuthentication
# 🌟 Import your celery task safely
from .tasks import send_transaction_email_task

class AccountListCreateView(generics.ListCreateAPIView):
    """
    Secure Account Vector.
    Allows authenticated users to list their existing asset pockets
    or provision fresh sub-wallets (Savings/Reserve).
    """
    serializer_class = AssetAccountSerializer
    authentication_classes = [CustomCookieJWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        """
        Strict Data Isolation Guard: Users can ONLY see or query
        accounts belonging directly to their own user profile.
        """
        return AssetAccount.objects.filter(user=self.request.user, is_active=True)


class TransferFundsView(generics.CreateAPIView):
    """
    Secure Transaction Processing Vector.
    Executes a thread-safe atomic double-entry bookkeeping asset transfer.
    """
    serializer_class = TransferFundsSerializer
    authentication_classes = [CustomCookieJWTAuthentication]
    permission_classes = [IsAuthenticated]

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        
        # 1. Execute the ultra-fast database balance movement
        tx = serializer.save()

        # 2. 🚀 THE CELERY HANDOFF TO CLOUDAMQP
        # Fires the async background task using the cloud broker instance
        send_transaction_email_task.delay(tx.id)

        return Response(
            {
                "status": "SUCCESS",
                "message": "Asset allocation transferred successfully.",
                "transaction_id": tx.id,
                "amount": str(tx.amount)
            },
            status=status.HTTP_201_CREATED
        )