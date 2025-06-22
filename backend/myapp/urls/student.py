from django.urls import path
from ..views.student import StudentProfileView, StudentProfileUpdateView

urlpatterns = [
    path('profile/', StudentProfileView.as_view(), name='student-profile'),
    path('profile/update/', StudentProfileUpdateView.as_view(), name='student-profile-update'),
]