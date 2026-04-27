from rest_framework import serializers
from .models import User, Business, ActivityLog
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

class BusinessSerializer(serializers.ModelSerializer):
    class Meta:
        model = Business
        fields = '__all__'

class UserSerializer(serializers.ModelSerializer):
    business = BusinessSerializer(read_only=True)
    class Meta:
        model = User
        fields = ('id', 'email', 'business', 'role')

class RegisterSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)
    business_name = serializers.CharField(write_only=True)
    gstin = serializers.CharField(max_length=15, write_only=True)
    state = serializers.CharField(write_only=True)
    address = serializers.CharField(write_only=True)

    def create(self, validated_data):
        business = Business.objects.create(
            name=validated_data['business_name'],
            gstin=validated_data['gstin'],
            state=validated_data['state'],
            address=validated_data['address']
        )
        user = User.objects.create_user(
            email=validated_data['email'],
            password=validated_data['password'],
            business=business
        )
        return user

class MyTokenObtainPairSerializer(TokenObtainPairSerializer):
    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        token['business_id'] = user.business.id if user.business else None
        return token

class ActivityLogSerializer(serializers.ModelSerializer):
    user_email = serializers.ReadOnlyField(source='user.email')
    class Meta:
        model = ActivityLog
        fields = ('id', 'user_email', 'action', 'model_name', 'object_id', 'timestamp', 'ip_address', 'details')
