from django.http import Http404
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.db.models import Q, Count
from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from stripe import Event

from ..models import EventComment, EventMedia, EventParticipant, EventTag
from ..serializers.events import EventCommentSerializer, EventDetailSerializer, EventMediaSerializer, EventParticipantSerializer, EventSerializer, EventTagSerializer
from ..models import CustomUser

class EventListCreateView(APIView):
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        """
        List all events the user can access (public events and private events they're invited to)
        Supports filtering by various parameters
        """
        # Get query parameters
        event_type = request.query_params.get('event_type')
        tag = request.query_params.get('tag')
        search = request.query_params.get('search')
        date_from = request.query_params.get('date_from')
        date_to = request.query_params.get('date_to')
        my_events = request.query_params.get('my_events') == 'true'
        participating = request.query_params.get('participating') == 'true'
        
        # Base queryset
        if my_events:
            # Events created by current user
            queryset = Event.objects.filter(creator=request.user)
        elif participating:
            # Events the user is participating in
            user_events = EventParticipant.objects.filter(
                user=request.user,
                status='going'
            ).values_list('event_id', flat=True)
            queryset = Event.objects.filter(id__in=user_events)
        else:
            # All events user can access
            queryset = Event.objects.filter(
                Q(is_public=True) | 
                Q(participants__user=request.user)
            ).distinct()
        
        # Apply filters
        if event_type:
            queryset = queryset.filter(event_type=event_type)
        
        if tag:
            queryset = queryset.filter(tags__name=tag)
        
        if search:
            queryset = queryset.filter(
                Q(title__icontains=search) |
                Q(description__icontains=search) |
                Q(location__icontains=search)
            )
        
        if date_from:
            queryset = queryset.filter(start_time__gte=date_from)
        
        if date_to:
            queryset = queryset.filter(start_time__lte=date_to)
        
        # Order by start time (upcoming first)
        queryset = queryset.filter(end_time__gte=timezone.now()).order_by('start_time')
        
        serializer = EventSerializer(queryset, many=True, context={'request': request})
        return Response(serializer.data)
    
    def post(self, request):
        """Create a new event"""
        serializer = EventSerializer(data=request.data, context={'request': request})
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class EventDetailView(APIView):
    permission_classes = [IsAuthenticated]
    
    def get_object(self, pk):
        """Get event or return 404"""
        event = get_object_or_404(Event, pk=pk)
        
        # Check if user can access this event
        if not event.is_public:
            if not EventParticipant.objects.filter(event=event, user=self.request.user).exists():
                # If private event and user is not a participant, deny access
                raise Http404("Event not found")
        
        return event
    
    def get(self, request, pk):
        """Get event details"""
        event = self.get_object(pk)
        serializer = EventDetailSerializer(event, context={'request': request})
        return Response(serializer.data)
    
    def put(self, request, pk):
        """Update event"""
        event = self.get_object(pk)
        
        # Only the creator can update the event
        if event.creator != request.user:
            return Response(
                {"detail": "You don't have permission to edit this event"},
                status=status.HTTP_403_FORBIDDEN
            )
        
        serializer = EventSerializer(event, data=request.data, context={'request': request})
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    def delete(self, request, pk):
        """Delete event"""
        event = self.get_object(pk)
        
        # Only the creator can delete the event
        if event.creator != request.user:
            return Response(
                {"detail": "You don't have permission to delete this event"},
                status=status.HTTP_403_FORBIDDEN
            )
        
        event.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

class EventParticipationView(APIView):
    permission_classes = [IsAuthenticated]
    
    def post(self, request, pk):
        """Join an event or update participation status"""
        event = get_object_or_404(Event, pk=pk)
        
        # Check if event is full
        if (event.participants.filter(status='going').count() >= event.max_participants and 
            not EventParticipant.objects.filter(event=event, user=request.user).exists()):
            return Response(
                {"detail": "This event has reached its maximum capacity"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Get participation status
        status_value = request.data.get('status', 'going')
        if status_value not in [s[0] for s in EventParticipant.STATUS_CHOICES]:
            return Response(
                {"detail": f"Invalid status. Must be one of: {', '.join([s[0] for s in EventParticipant.STATUS_CHOICES])}"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Create or update participant
        participant, created = EventParticipant.objects.update_or_create(
            event=event,
            user=request.user,
            defaults={'status': status_value}
        )
        
        # If user is the creator, make sure they're an organizer
        if event.creator == request.user:
            participant.role = 'organizer'
            participant.save()
        
        serializer = EventParticipantSerializer(participant)
        return Response(serializer.data)
    
    def delete(self, request, pk):
        """Leave an event"""
        event = get_object_or_404(Event, pk=pk)
        
        # Creator can't leave their own event
        if event.creator == request.user:
            return Response(
                {"detail": "As the creator, you cannot leave your own event. You may delete it instead."},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Remove participation
        EventParticipant.objects.filter(event=event, user=request.user).delete()
        
        return Response(status=status.HTTP_204_NO_CONTENT)

class EventInviteView(APIView):
    permission_classes = [IsAuthenticated]
    
    def post(self, request, pk):
        """Invite users to an event"""
        event = get_object_or_404(Event, pk=pk)
        
        # Check if user has permission to invite (must be a participant)
        try:
            participant = EventParticipant.objects.get(event=event, user=request.user)
        except EventParticipant.DoesNotExist:
            return Response(
                {"detail": "You must be a participant to invite others"},
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Get user IDs to invite
        user_ids = request.data.get('user_ids', [])
        if not user_ids:
            return Response(
                {"detail": "No users specified to invite"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Invite users
        invited_count = 0
        for user_id in user_ids:
            try:
                user = CustomUser.objects.get(id=user_id)
                if not EventParticipant.objects.filter(event=event, user=user).exists():
                    EventParticipant.objects.create(
                        event=event,
                        user=user,
                        status='invited'
                    )
                    invited_count += 1
                    
                    # Send notification/email here
                    
            except CustomUser.DoesNotExist:
                pass
        
        return Response({"invited_count": invited_count})

class EventCommentView(APIView):
    permission_classes = [IsAuthenticated]
    
    def get(self, request, pk):
        """Get comments for an event"""
        event = get_object_or_404(Event, pk=pk)
        comments = EventComment.objects.filter(event=event).order_by('created_at')
        serializer = EventCommentSerializer(comments, many=True)
        return Response(serializer.data)
    
    def post(self, request, pk):
        """Add a comment to an event"""
        event = get_object_or_404(Event, pk=pk)
        
        # Check if user is a participant
        if not EventParticipant.objects.filter(event=event, user=request.user).exists():
            return Response(
                {"detail": "You must be a participant to comment"},
                status=status.HTTP_403_FORBIDDEN
            )
        
        serializer = EventCommentSerializer(data={
            'content': request.data.get('content')
        })
        
        if serializer.is_valid():
            comment = serializer.save(event=event, user=request.user)
            return Response(EventCommentSerializer(comment).data, status=status.HTTP_201_CREATED)
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class EventMediaView(APIView):
    permission_classes = [IsAuthenticated]
    
    def get(self, request, pk):
        """Get media for an event"""
        event = get_object_or_404(Event, pk=pk)
        media = EventMedia.objects.filter(event=event)
        serializer = EventMediaSerializer(media, many=True)
        return Response(serializer.data)
    
    def post(self, request, pk):
        """Add media to an event"""
        event = get_object_or_404(Event, pk=pk)
        
        # Check if user is a participant
        if not EventParticipant.objects.filter(event=event, user=request.user).exists():
            return Response(
                {"detail": "You must be a participant to add media"},
                status=status.HTTP_403_FORBIDDEN
            )
        
        serializer = EventMediaSerializer(data={
            'file': request.data.get('file'),
            'media_type': request.data.get('media_type'),
            'title': request.data.get('title', '')
        })
        
        if serializer.is_valid():
            media = serializer.save(event=event, uploaded_by=request.user)
            return Response(EventMediaSerializer(media).data, status=status.HTTP_201_CREATED)
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class EventTagsView(APIView):
    permission_classes = [AllowAny]
    
    def get(self, request):
        """Get popular event tags"""
        tags = EventTag.objects.annotate(
            usage_count=Count('events')
        ).order_by('-usage_count')[:20]  # Top 20 tags
        
        serializer = EventTagSerializer(tags, many=True)
        return Response(serializer.data)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def join_event_by_invite(request, invite_link):
    """Join an event using an invite link"""
    try:
        event = Event.objects.get(invite_link=invite_link)
    except Event.DoesNotExist:
        return Response({"detail": "Invalid invite link"}, status=status.HTTP_404_NOT_FOUND)
    
    # Check if event is full
    if event.participants.filter(status='going').count() >= event.max_participants:
        return Response(
            {"detail": "This event has reached its maximum capacity"},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    # Add user as participant
    participant, created = EventParticipant.objects.get_or_create(
        event=event,
        user=request.user,
        defaults={'status': 'going'}
    )
    
    if not created:
        participant.status = 'going'
        participant.save()
    
    serializer = EventDetailSerializer(event, context={'request': request})
    return Response(serializer.data)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def upcoming_events(request):
    """Get upcoming events the user is participating in"""
    now = timezone.now()
    
    # Get events where the user is participating with status "going"
    user_events = EventParticipant.objects.filter(
        user=request.user,
        status='going',
        event__start_time__gt=now
    ).values_list('event_id', flat=True)
    
    events = Event.objects.filter(
        id__in=user_events
    ).order_by('start_time')[:5]  # Get next 5 events
    
    serializer = EventSerializer(events, many=True, context={'request': request})
    return Response(serializer.data)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def recommended_events(request):
    """Get recommended events based on user interests and past participation"""
    now = timezone.now()
    user = request.user
    
    # Get user's past events
    past_events = EventParticipant.objects.filter(
        user=user,
        status='going',
        event__end_time__lt=now
    ).values_list('event_id', flat=True)
    
    # Get event types user has participated in
    event_types = Event.objects.filter(
        id__in=past_events
    ).values_list('event_type', flat=True).distinct()
    
    # Get tags from events user has participated in
    tags = Event.objects.filter(
        id__in=past_events
    ).values_list('tags__name', flat=True).distinct()
    
    # Find upcoming events that match user interests
    if hasattr(user, 'student_profile'):
        hobbies = user.student_profile.hobbies
    else:
        hobbies = ""
    
    recommended = Event.objects.filter(
        Q(is_public=True) &
        Q(end_time__gt=now) &
        (
            Q(event_type__in=event_types) |
            Q(tags__name__in=tags) |
            Q(description__icontains=hobbies) |
            Q(title__icontains=hobbies)
        )
    ).exclude(
        participants__user=user  # Exclude events user is already participating in
    ).distinct().order_by('start_time')[:10]
    
    serializer = EventSerializer(recommended, many=True, context={'request': request})
    return Response(serializer.data)