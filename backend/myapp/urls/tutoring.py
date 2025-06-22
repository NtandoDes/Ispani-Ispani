from django.urls import path, include
from rest_framework.routers import DefaultRouter

from ..views import (
    TutorViewSet, StudentViewSet, SubjectViewSet, TutorDetailView,
    BookingViewSet, ReviewViewSet, StudentUserDetailView
)

router = DefaultRouter()
router.register(r'tutors', TutorViewSet)
router.register(r'students', StudentViewSet)
router.register(r'subjects', SubjectViewSet)
router.register(r'bookings', BookingViewSet)
router.register(r'reviews', ReviewViewSet)

urlpatterns = [
    path('', include(router.urls)),
    path('tutors/my-earnings/', TutorViewSet.as_view({'get': 'my_earnings'}), name='my-earnings'),
    path('user/student/<int:user_id>/', StudentUserDetailView.as_view(), name='student-user-detail'),
    path('user/tutor/<int:user_id>/', TutorDetailView.as_view(), name='tutor-user-detail'),
]