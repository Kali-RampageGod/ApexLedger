from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework.exceptions import AuthenticationFailed

class CustomCookieJWTAuthentication(JWTAuthentication):
    """
    Custom Security Guard Interceptor.
    Extracts access tokens from hidden browser cookies instead of raw headers.
    """
    def authenticate(self, request):
        # Read the raw string token from the browser cookie jar
        raw_token = request.COOKIES.get('access_token')
        
        if raw_token is None:
            return None

        # Validate the token structure using standard simplejwt validation tools
        validated_token = self.get_validated_token(raw_token)
        
        # Pull the matching User record linked to this token
        user = self.get_user(validated_token)
        
        # Compliance Check: If our system has frozen this user, block them immediately
        if user.is_frozen:
            raise AuthenticationFailed("This account has been frozen due to compliance/security parameters.")
            
        return (user, validated_token)