from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import RegisterView, BusinessView, MyTokenObtainPairView, ActivityLogViewSet, UserViewSet
from rest_framework_simplejwt.views import TokenRefreshView

router = DefaultRouter()
router.register(r'logs', ActivityLogViewSet, basename='activity-logs')
router.register(r'users', UserViewSet, basename='users')

urlpatterns = [
    path('register/', RegisterView.as_view(), name='register'),
    path('login/', MyTokenObtainPairView.as_view(), name='login'),
    path('token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('business/', BusinessView.as_view(), name='business'),
    path('', include(router.urls)),
]
