from rest_framework import serializers
from ..models import ChatMessage, MessageAttachment, ChatRoom, PrivateChat, PrivateMessage
from ..serializers.authentication import UserBasicSerializer, UserSerializer

class ChatRoomSerializer(serializers.ModelSerializer):
    members = UserSerializer(many=True, read_only=True)

    class Meta:
        model = ChatRoom
        fields = ['id', 'name', 'chat_type', 'members', 'created_at']

class MessageAttachmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = MessageAttachment
        fields = ['id', 'file', 'attachment_type', 'thumbnail']

class ChatMessageSerializer(serializers.ModelSerializer):
    sender = UserSerializer(read_only=True)
    attachments = MessageAttachmentSerializer(many=True, read_only=True)

    class Meta:
        model = ChatMessage
        fields = ['id', 'room', 'sender', 'text', 'attachments', 'created_at'] 
        read_only_fields = ['sender', 'created_at']

class PrivateChatSerializer(serializers.ModelSerializer):
    user1 = UserBasicSerializer(read_only=True)
    user2 = UserBasicSerializer(read_only=True)
    other_user = serializers.SerializerMethodField()
    last_message = serializers.SerializerMethodField()
    unread_count = serializers.SerializerMethodField()
    
    class Meta:
        model = PrivateChat
        fields = ['id', 'user1', 'user2', 'other_user', 'created_at', 'last_message', 'unread_count']
    
    def get_other_user(self, obj):
        request = self.context.get('request')
        if request and request.user:
            other_user = obj.user2 if obj.user1 == request.user else obj.user1
            return UserBasicSerializer(other_user).data
        return None
    
    def get_last_message(self, obj):
        last_message = obj.messages.order_by('-created_at').first()
        if last_message:
            return {
                'content': last_message.content,
                'sender': last_message.sender.username,
                'created_at': last_message.created_at,
                'is_read': last_message.is_read
            }
        return None
    
    def get_unread_count(self, obj):
        request = self.context.get('request')
        if request and request.user:
            return obj.messages.filter(sender=request.user, is_read=False).count()
        return 0

class PrivateMessageSerializer(serializers.ModelSerializer):
    sender = UserBasicSerializer(read_only=True)
    
    class Meta:
        model = PrivateMessage
        fields = ['id', 'content', 'sender', 'chat', 'created_at', 'is_read']
        read_only_fields = ['sender', 'chat', 'created_at']