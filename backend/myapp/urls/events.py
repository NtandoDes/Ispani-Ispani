from django.urls import path

from ..views import EventCommentView, EventDetailView, EventInviteView, EventListCreateView, EventMediaView, EventParticipationView, EventTagsView, join_event_by_invite, recommended_events, upcoming_events
from ..views import *

urlpatterns = [
   # Event URLs
    path('events/', EventListCreateView.as_view(), name='event-list-create'),
    path('events/<int:pk>/', EventDetailView.as_view(), name='event-detail'),
    path('events/<int:pk>/participate/', EventParticipationView.as_view(), name='event-participate'),
    path('events/<int:pk>/invite/', EventInviteView.as_view(), name='event-invite'),
    path('events/<int:pk>/comments/', EventCommentView.as_view(), name='event-comments'),
    path('events/<int:pk>/media/', EventMediaView.as_view(), name='event-media'),
    path('events/tags/', EventTagsView.as_view(), name='event-tags'),
    path('events/invite/<str:invite_link>/', join_event_by_invite, name='join-event-by-invite'),
    path('events/upcoming/', upcoming_events, name='upcoming-events'),
    path('events/recommended/', recommended_events, name='recommended-events'),

]

