from django.shortcuts import get_object_or_404
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework import generics, status
from django.db.models import Q

from ..models.authentication import ConnectionRequest
from ..models import CustomUser,ChatRoom, ChatMessage, PrivateChat, PrivateMessage
from ..serializers.messaging import ChatMessageSerializer, ChatRoomSerializer,PrivateChatSerializer, PrivateMessageSerializer

class ChatRoomListCreateView(generics.ListCreateAPIView):
    queryset = ChatRoom.objects.all()
    serializer_class = ChatRoomSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        """Override to add last message info"""
        rooms = ChatRoom.objects.all()
        return rooms

    def list(self, request, *args, **kwargs):
        """Override list to include last message for each room"""
        queryset = self.get_queryset()
        serializer = self.get_serializer(queryset, many=True)
        
        # Add last message info to each room
        rooms_data = []
        for room_data in serializer.data:
            room_id = room_data['id']
            
            # Get last message for this room
            last_message = ChatMessage.objects.filter(
                room_id=room_id
            ).order_by('-created_at').first()
            
            if last_message:
                room_data['last_message'] = {
                    'text': last_message.text,
                    'sender': last_message.sender.username,
                    'created_at': last_message.created_at.isoformat()
                }
            else:
                room_data['last_message'] = None
                
            rooms_data.append(room_data)
        
        # Sort by last message timestamp (rooms with recent messages first)
        rooms_data.sort(
            key=lambda x: x['last_message']['created_at'] if x['last_message'] else '', 
            reverse=True
        )
        
        return Response(rooms_data)

class ChatMessageListView(generics.ListAPIView):
    serializer_class = ChatMessageSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        room_id = self.kwargs['room_id']
        return ChatMessage.objects.filter(room_id=room_id).order_by('created_at')

class SendMessageView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, room_id):
        room = get_object_or_404(ChatRoom, id=room_id)
        serializer = ChatMessageSerializer(data=request.data)
        if serializer.is_valid():
            message = serializer.save(sender=request.user, room=room)
            
            if hasattr(room, 'updated_at'):
                room.save(update_fields=['updated_at'])
            
            return Response(serializer.data, status=201)
        return Response(serializer.errors, status=400)

class PrivateChatListCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        """Get all chats for the current user"""
        user = request.user
        chats = PrivateChat.objects.filter(
            Q(user1=user) | Q(user2=user)
        ).order_by('created_at')
        
        serializer = PrivateChatSerializer(chats, many=True, context={'request': request})
        return Response(serializer.data)

    def post(self, request):
        """Create a new chat or return existing one"""
        user1 = request.user
        user2_id = request.data.get("user2_id")
        
        if not user2_id:
            return Response({
                'error': 'user2_id is required'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        user2 = get_object_or_404(CustomUser, id=user2_id)
        
        # Can't chat with yourself
        if user1 == user2:
            return Response({
                'error': 'Cannot create chat with yourself'
            }, status=status.HTTP_400_BAD_REQUEST)

        # Check if users are connected - FIXED: using correct field names
        connection = ConnectionRequest.objects.filter(
            Q(from_user=user1, to_user=user2) | Q(from_user=user2, to_user=user1),
            status='accepted'
        ).first()

        if not connection:
            return Response({
                'error': 'You can only message users you are connected with'
            }, status=status.HTTP_403_FORBIDDEN)

        # Get or create chat (ensuring consistent user ordering)
        chat, created = PrivateChat.objects.get_or_create(
            user1=min(user1, user2, key=lambda u: u.id),
            user2=max(user1, user2, key=lambda u: u.id)
        )
        
        serializer = PrivateChatSerializer(chat, context={'request': request})
        return Response(serializer.data, status=201 if created else 200)


class CreatePrivateChatView(APIView):
    """Alternative endpoint that matches your Flutter code's expected path"""
    permission_classes = [IsAuthenticated]

    def post(self, request, user_id):
        """Create or get existing chat with specific user"""
        try:
            current_user = request.user
            other_user = get_object_or_404(CustomUser, id=user_id)
            
            # Can't chat with yourself
            if current_user == other_user:
                return Response({
                    'error': 'Cannot create chat with yourself'
                }, status=status.HTTP_400_BAD_REQUEST)

            # Check if users are connected - FIXED: using correct field names
            connection = ConnectionRequest.objects.filter(
                Q(from_user=current_user, to_user=other_user) | 
                Q(from_user=other_user, to_user=current_user),
                status='accepted'
            ).first()

            if not connection:
                return Response({
                    'error': 'Cannot create chat - users are not connected'
                }, status=status.HTTP_403_FORBIDDEN)

            # Check if chat already exists
            existing_chat = PrivateChat.objects.filter(
                Q(user1=current_user, user2=other_user) |
                Q(user1=other_user, user2=current_user)
            ).first()

            if existing_chat:
                return Response({
                    'id': existing_chat.id,
                    'user1': {
                        'id': existing_chat.user1.id, 
                        'username': existing_chat.user1.username,
                        'display_name': getattr(existing_chat.user1, 'display_name', existing_chat.user1.username)
                    },
                    'user2': {
                        'id': existing_chat.user2.id, 
                        'username': existing_chat.user2.username,
                        'display_name': getattr(existing_chat.user2, 'display_name', existing_chat.user2.username)
                    },
                    'created_at': existing_chat.created_at,
                    'updated_at': existing_chat.updated_at
                }, status=200)

            # Create new chat (ensure consistent user ordering)
            chat = PrivateChat.objects.create(
                user1=min(current_user, other_user, key=lambda u: u.id),
                user2=max(current_user, other_user, key=lambda u: u.id)
            )

            return Response({
                'id': chat.id,
                'user1': {
                    'id': chat.user1.id, 
                    'username': chat.user1.username,
                    'display_name': getattr(chat.user1, 'display_name', chat.user1.username)
                },
                'user2': {
                    'id': chat.user2.id, 
                    'username': chat.user2.username,
                    'display_name': getattr(chat.user2, 'display_name', chat.user2.username)
                },
                'created_at': chat.created_at,
                'updated_at': chat.updated_at
            }, status=201)

        except Exception as e:
            return Response({
                'error': f'Internal server error: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class PrivateMessageListView(generics.ListAPIView):
    serializer_class = PrivateMessageSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        other_user_id = self.kwargs['user_id']
        other_user = get_object_or_404(CustomUser, id=other_user_id)
        
        # Check if users are connected - FIXED: using correct field names
        connection = ConnectionRequest.objects.filter(
            Q(from_user=self.request.user, to_user=other_user) | 
            Q(from_user=other_user, to_user=self.request.user),
            status='accepted'
        ).first()

        if not connection:
            return PrivateMessage.objects.none()

        # Get or create chat automatically
        chat = PrivateChat.objects.filter(
            Q(user1=self.request.user, user2=other_user) |
            Q(user1=other_user, user2=self.request.user)
        ).first()

        if not chat:
            return PrivateMessage.objects.none()
            
        return PrivateMessage.objects.filter(chat=chat).order_by('created_at')


class SendPrivateMessageView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, user_id):
        other_user = get_object_or_404(CustomUser, id=user_id)
        
        # Check if users are connected - FIXED: using correct field names
        connection = ConnectionRequest.objects.filter(
            Q(from_user=request.user, to_user=other_user) | 
            Q(from_user=other_user, to_user=request.user),
            status='accepted'
        ).first()

        if not connection:
            return Response({
                'error': 'Cannot send message - users are not connected'
            }, status=status.HTTP_403_FORBIDDEN)

        # Get or create chat automatically
        chat = PrivateChat.objects.filter(
            Q(user1=request.user, user2=other_user) |
            Q(user1=other_user, user2=request.user)
        ).first()

        if not chat:
            # Create new chat with consistent ordering
            if request.user.id < other_user.id:
                chat = PrivateChat.objects.create(user1=request.user, user2=other_user)
            else:
                chat = PrivateChat.objects.create(user1=other_user, user2=request.user)

        serializer = PrivateMessageSerializer(data=request.data)
        if serializer.is_valid():
            message = serializer.save(sender=request.user, chat=chat)
            
            # Update chat's updated_at timestamp
            chat.save(update_fields=['created_at'])
            
            # Include chat_id in response
            response_data = serializer.data
            response_data['chat_id'] = chat.id
            
            return Response(response_data, status=201)
        return Response(serializer.errors, status=400)


class UserChatsListView(APIView):
    """Get all users that current user can start a chat with and existing chats"""
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        current_user = request.user
        
        # Get all connected users - FIXED: using correct field names
        connections = ConnectionRequest.objects.filter(
            Q(from_user=current_user) | Q(to_user=current_user),
            status='accepted'
        )
        
        connected_users = []
        for connection in connections:
            other_user = connection.to_user if connection.from_user == current_user else connection.from_user
            
            # Check if chat already exists
            existing_chat = PrivateChat.objects.filter(
                Q(user1=current_user, user2=other_user) |
                Q(user1=other_user, user2=current_user)
            ).first()
            
            # Get last message if chat exists
            last_message = None
            if existing_chat:
                last_msg = PrivateMessage.objects.filter(chat=existing_chat).order_by('-created_at').first()
                if last_msg:
                    last_message = {
                        'content': last_msg.content,
                        'sender': last_msg.sender.username,
                        'created_at': last_msg.created_at.isoformat()
                    }
            
            user_data = {
                'id': other_user.id,
                'username': other_user.username,
                'display_name': getattr(other_user, 'display_name', other_user.username),
                'has_existing_chat': bool(existing_chat),
                'chat_id': existing_chat.id if existing_chat else None,
                'last_message': last_message,
                'created_at': existing_chat.updated_at.isoformat() if existing_chat else None
            }
            connected_users.append(user_data)
        
        # Sort by last activity (chats with recent messages first)
        # FIXED: there was a typo in the original code (' created_at' with space)
        connected_users.sort(key=lambda x: x['created_at'] or '', reverse=True)
        
        return Response(connected_users)