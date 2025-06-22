from django.urls import path
from ..views.groups import DynamicGroupsView, GroupListCreate,CreateGroupView, JoinGroupView, JoinableGroupsView,LeaveGroupView, InstitutionGroupsView, CityHobbyGroupsView, GroupSuggestionsView,JoinedGroupsView, UnifiedGroupCreateView


urlpatterns = [

   # path('groups/<uuid:group_id>/icon/', UploadGroupIconView.as_view(), name='upload-icon'),
   # path('notifications/', GetNotificationsView.as_view(), name='get-notifications'),
    path('groups/joined/', JoinedGroupsView.as_view(), name='joined-groups'),
    path('groups/joinable/', JoinableGroupsView.as_view(), name='joinable-groups'),
    path('groups/', GroupListCreate.as_view(), name='group-list-create'),
    path('groups/dynamic/', DynamicGroupsView.as_view(), name='dynamic-groups'),
    path('groups/create/', CreateGroupView.as_view(), name='create-group'),
    path('groups/build/', UnifiedGroupCreateView.as_view(), name='create_group'),
    path('groups/<int:group_id>/join/', JoinGroupView.as_view(), name='join-group'),
    path('groups/<int:group_id>/leave/', LeaveGroupView.as_view(), name='leave-group'),
    path('groups/my-institution/', InstitutionGroupsView.as_view(), name='institution-groups'),
    path('groups/my-city-hobbies/', CityHobbyGroupsView.as_view(), name='city-hobby-groups'),
    path('groups/suggestions/',GroupSuggestionsView.as_view(), name='group-suggestions'),
]
