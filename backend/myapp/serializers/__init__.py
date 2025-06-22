# serializers/__init__.py
from .tutoring import BookingSerializer
from .authentication import UserSerializer, UserRegistrationSerializer
from .groups import GroupCreateSerializer, GroupChatSerializer
from .events import (
    EventCommentSerializer,
    EventDetailSerializer,
    EventMediaSerializer,
    EventParticipantSerializer,
    EventSerializer,
    EventTagSerializer
)

__all__ = [
    "BookingSerializer",
    "UserSerializer",
    "UserRegistrationSerializer",
    "GroupCreateSerializer",
    "GroupChatSerializer",
    "EventCommentSerializer",
    "EventDetailSerializer",
    "EventMediaSerializer",
    "EventParticipantSerializer",
    "EventSerializer",
    "EventTagSerializer",
]
