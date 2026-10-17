from django.urls import path
from .views import AccountListCreateView, TransferFundsView

urlpatterns = [
    path('pockets/', AccountListCreateView.as_view(), name='account_list_create'),
    path('transfer/', TransferFundsView.as_view(), name='transfer_funds'), # 🌟 Added
]