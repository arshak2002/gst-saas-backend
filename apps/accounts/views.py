from rest_framework import status, views, response, permissions, viewsets
from rest_framework_simplejwt.views import TokenObtainPairView
from .serializers import RegisterSerializer, BusinessSerializer, MyTokenObtainPairSerializer, ActivityLogSerializer, UserSerializer
from .models import Business, ActivityLog, User
from apps.subscriptions.permissions import HasUserQuota

class IsAdminOrStaff(permissions.BasePermission):
    def has_permission(self, request, view):
        return request.user.role in ['ADMIN', 'STAFF']

class RegisterView(views.APIView):
    permission_classes = [permissions.AllowAny]
    def post(self, request):
        serializer = RegisterSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return response.Response(serializer.data, status=status.HTTP_201_CREATED)
        return response.Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class BusinessView(views.APIView):
    def get(self, request):
        serializer = BusinessSerializer(request.user.business)
        return response.Response(serializer.data)

    def put(self, request):
        serializer = BusinessSerializer(request.user.business, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return response.Response(serializer.data)
        return response.Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class UserViewSet(viewsets.ModelViewSet):
    serializer_class = UserSerializer
    
    def get_queryset(self):
        return User.objects.filter(business=self.request.user.business)

    def get_permissions(self):
        if self.action == 'create':
            return [permissions.IsAuthenticated(), IsAdminOrStaff(), HasUserQuota()]
        if self.action in ['update', 'partial_update', 'destroy']:
            return [permissions.IsAuthenticated(), IsAdminOrStaff()]
        return [permissions.IsAuthenticated()]

    def perform_create(self, serializer):
        serializer.save(business=self.request.user.business)

class MyTokenObtainPairView(TokenObtainPairView):
    serializer_class = MyTokenObtainPairSerializer

class ActivityLogViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = ActivityLog.objects.all()
    serializer_class = ActivityLogSerializer

    def get_queryset(self):
        return self.queryset.filter(business=self.request.user.business)
