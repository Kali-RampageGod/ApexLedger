from django.conf import settings
from rest_framework import status, generics
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.views import TokenObtainPairView

from .serializers import CustomTokenObtainPairSerializer, UserRegistrationSerializer


class RegisterView(generics.CreateAPIView):
    """
    Onboarding Endpoint for new customers.
    """
    serializer_class = UserRegistrationSerializer
    authentication_classes = []
    permission_classes = []


class LoginView(TokenObtainPairView):
    """
    Secure Login Vector.
    Takes credentials, converts them to JWT structures, and embeds them into HttpOnly cookies.
    """
    serializer_class = CustomTokenObtainPairSerializer

    def post(self, request, *args, **kwargs):
        response = super().post(request, *args, **kwargs)
        
        if response.status_code == 200:
            access_token = response.data.get('access')
            refresh_token = response.data.get('refresh')

            # Strip the exposed raw strings out of the public JSON response body text
            del response.data['access']
            del response.data['refresh']
            response.data['message'] = "Identity verification cleared successfully."

            # Set the Access Token inside an HttpOnly cookie (short expiration life)
            response.set_cookie(
                key='access_token',
                value=access_token,
                httponly=True,
                secure=not settings.DEBUG,  # True in production (requires HTTPS)
                samesite='Lax',
                max_age=300                 # 5 minutes validation lifetime
            )

            # Set the Refresh Token inside a separate HttpOnly cookie (longer lifetime)
            response.set_cookie(
                key='refresh_token',
                value=refresh_token,
                httponly=True,
                secure=not settings.DEBUG,
                samesite='Lax',
                max_age=86400                # 24 hours lifecycle allocation
            )

        return response


class LogoutView(APIView):
    """
    Terminates browser session controls securely by wiping the client cookies.
    """
    def post(self, request):
        response = Response({"message": "Session terminated successfully."}, status=status.HTTP_200_OK)
        
        # Forcefully flush cookie values on the browser client immediately
        response.delete_cookie('access_token')
        response.delete_cookie('refresh_token')
        return response