from django.urls import path
from ..views.authentication import CompleteRegistrationView, ConnectionsListView, IncomingRequestsView,  LoginView, LogoutView, MutualConnectionsView, OutgoingRequestsView, ProfileView, RespondToRequestView, SendConnectionRequestView, SignUpView, SuggestedUsersView, UserDetailView, VerifyOTPView,ForgotPasswordView,ResetPasswordView,DeleteAccountView,SwitchRoleView, get_user_by_id, remove_profile_picture, upload_profile_picture

urlpatterns = [
    # Authentication URLs
    path('signup/', SignUpView.as_view(), name='signup'),
    path('verify-otp/', VerifyOTPView.as_view(), name='verify-otp'),
    path('complete-registration/', CompleteRegistrationView.as_view(), name='complete-registration'),
    path('login/', LoginView.as_view(), name='login'),
    path('logout/', LogoutView.as_view(), name='logout'),
    path("switch-role/", SwitchRoleView.as_view(), name="switch-role"),
    path('forgot-password/', ForgotPasswordView.as_view(), name='forgot-password'),
    path('reset-password/', ResetPasswordView.as_view(), name='reset-password'),
    path('account/delete/', DeleteAccountView.as_view(), name='account-delete'),

    path('user/<int:user_id>/', UserDetailView.as_view(), name='user-detail'),
    path('user/details/<int:user_id>/', UserDetailView.as_view(), name='user-detail-alt'),
    path('profile/<int:user_id>/', get_user_by_id, name='public-user-profile'),

    # Profile endpoints
    path('user/profile/', ProfileView.as_view(), name='user-profile'),
    path('user/profile/picture/upload/', upload_profile_picture, name='upload-profile-picture'),
    path('user/profile/picture/remove/', remove_profile_picture, name='remove-profile-picture'),
    path('user/<int:user_id>/', get_user_by_id, name='get-user-by-id'),

    path('suggested-users/', SuggestedUsersView.as_view(), name='suggested-users'),
    path('send-request/', SendConnectionRequestView.as_view(), name='send-request'),
    path('respond-request/<int:pk>/', RespondToRequestView.as_view(), name='respond-request'),
    path('incoming-requests/', IncomingRequestsView.as_view(), name='incoming-requests'),
    path('outgoing-requests/', OutgoingRequestsView.as_view(), name='outgoing-requests'),
    path('connections/', ConnectionsListView.as_view(), name='connections'),
    path('mutual-connections/<int:user_id>/', MutualConnectionsView.as_view(), name='mutual-connections'),

]