from django.urls import path,re_path
from ..views import *
from .. import views
from ..views import PrivateChatListCreateView
from .. import consumers 

urlpatterns = [
    # Chat URLs
    path('chat/rooms/', views.ChatRoomListCreateView.as_view(), name='chat-room-list'),
    path('chat/rooms/<int:room_id>/messages/', views.ChatMessageListView.as_view(), name='room-messages'),
    path('chat/rooms/<int:room_id>/send/', views.SendMessageView.as_view(), name='send-message'),
    
    # Private Chat URLs
    path('chat/private/', views.PrivateChatListCreateView.as_view(), name='private-chat'),
    path('chat/create/<int:user_id>/', CreatePrivateChatView.as_view(), name='create-private-chat'),
    path('chat/private/<int:user_id>/messages/', views.PrivateMessageListView.as_view(), name='private-messages'),
    path('chat/private/<int:user_id>/send/', views.SendPrivateMessageView.as_view(), name='send-private-message'),
    path('chat/users/', views.UserChatsListView.as_view(), name='user-chats-list'),
]

