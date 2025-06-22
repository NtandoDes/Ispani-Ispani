from django.utils.crypto import get_random_string
from rest_framework import serializers
from ..models import EventComment, EventMedia, EventParticipant, EventTag, Event
from .authentication import UserSerializer


class EventTagSerializer(serializers.ModelSerializer):
    class Meta:
        model = EventTag
        fields = ['id', 'name']

class EventMediaSerializer(serializers.ModelSerializer):
    uploaded_by = serializers.StringRelatedField()
    
    class Meta:
        model = EventMedia
        fields = ['id', 'file', 'media_type', 'title', 'uploaded_by', 'uploaded_at']

class EventCommentSerializer(serializers.ModelSerializer):
    user = serializers.StringRelatedField()
    user_id = serializers.IntegerField(source='user.id', read_only=True)
    
    class Meta:
        model = EventComment
        fields = ['id', 'user', 'user_id', 'content', 'created_at']
        read_only_fields = ['user', 'created_at']

class EventParticipantSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)
    
    class Meta:
        model = EventParticipant
        fields = ['id', 'user', 'role', 'status', 'joined_at']
        read_only_fields = ['joined_at']

class EventSerializer(serializers.ModelSerializer):
    creator = UserSerializer(read_only=True)
    participants_count = serializers.SerializerMethodField()
    is_creator = serializers.SerializerMethodField()
    user_status = serializers.SerializerMethodField()
    tags = EventTagSerializer(many=True, read_only=True)
    tag_names = serializers.ListField(child=serializers.CharField(), write_only=True, required=False)
    
    class Meta:
        model = Event
        fields = [
            'id', 'title', 'description', 'event_type', 'creator', 'location', 
            'start_time', 'end_time', 'max_participants', 'is_public', 
            'recurrence', 'recurrence_end_date', 'created_at', 'updated_at',
            'invite_link', 'participants_count', 'is_creator', 'user_status',
            'tags', 'tag_names'
        ]
        read_only_fields = ['creator', 'created_at', 'updated_at', 'invite_link']
    
    def get_participants_count(self, obj):
        return obj.participants.filter(status='going').count()
    
    def get_is_creator(self, obj):
        request = self.context.get('request')
        if request and hasattr(request, 'user'):
            return obj.creator == request.user
        return False
    
    def get_user_status(self, obj):
        request = self.context.get('request')
        if request and hasattr(request, 'user') and request.user.is_authenticated:
            try:
                participant = EventParticipant.objects.get(event=obj, user=request.user)
                return participant.status
            except EventParticipant.DoesNotExist:
                return None
        return None
    
    def create(self, validated_data):
        tag_names = validated_data.pop('tag_names', [])
        request = self.context.get('request')
        
        # Generate invite link
        invite_link = get_random_string(20)
        
        event = Event.objects.create(
            creator=request.user,
            invite_link=invite_link,
            **validated_data
        )
        
        # Add creator as organizer
        EventParticipant.objects.create(
            event=event,
            user=request.user,
            role='organizer',
            status='going'
        )
        
        # Process tags
        for tag_name in tag_names:
            tag, created = EventTag.objects.get_or_create(name=tag_name.lower().strip())
            event.tags.add(tag)
            
        return event
    
    def update(self, instance, validated_data):
        tag_names = validated_data.pop('tag_names', None)
        
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        
        instance.save()
        
        # Update tags if provided
        if tag_names is not None:
            instance.tags.clear()
            for tag_name in tag_names:
                tag, created = EventTag.objects.get_or_create(name=tag_name.lower().strip())
                instance.tags.add(tag)
                
        return instance

class EventDetailSerializer(EventSerializer):
    participants = EventParticipantSerializer(many=True, read_only=True)
    comments = EventCommentSerializer(many=True, read_only=True)
    media = EventMediaSerializer(many=True, read_only=True)
    
    class Meta(EventSerializer.Meta):
        fields = EventSerializer.Meta.fields + ['participants', 'comments', 'media']
