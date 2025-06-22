from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.permissions import IsAuthenticatedOrReadOnly
from rest_framework.response import Response
from rest_framework import status, generics
import json
from django.contrib.auth.models import Group
from django.db.models import Q, Count
from django.db import transaction

from ..models.groups import GroupChat
from ..models import ChatRoom  
from ..serializers.groups import GroupChatSerializer, GroupCreateSerializer


def get_user_profile(user):
    """Returns the profile and type based on available user role."""
    role_attrs = ['student_profile', 'hstudent_profile', 'serviceprovider_profile', 'jobseeker_profile', 'tutor_profile']
    for attr in role_attrs:
        if hasattr(user, attr):
            return getattr(user, attr), attr
    return None, None


def get_user_hobbies(profile):
    """Safely extract hobbies from profile, handling both ManyToMany and string formats."""
    if not profile:
        return []
    
    if hasattr(profile, 'hobbies'):
        hobbies_field = profile.hobbies
        
        # Check if it's a ManyToMany manager
        if hasattr(hobbies_field, 'all'):
            return list(hobbies_field.all())
        
        # Check if it's a string (JSON or comma-separated)
        elif isinstance(hobbies_field, str):
            try:
                # Try to parse as JSON first
                if hobbies_field.startswith('[') or hobbies_field.startswith('{'):
                    parsed_hobbies = json.loads(hobbies_field)
                    if isinstance(parsed_hobbies, list):
                        return parsed_hobbies
                # Otherwise treat as comma-separated
                else:
                    return [h.strip() for h in hobbies_field.split(',') if h.strip()]
            except (json.JSONDecodeError, AttributeError):
                # If JSON parsing fails, try comma-separated
                return [h.strip() for h in str(hobbies_field).split(',') if h.strip()]
        
        # If it's already a list
        elif isinstance(hobbies_field, list):
            return hobbies_field
    
    return []


def assign_user_to_dynamic_group(user, role, city, institution=None, qualification=None):
    """Create and assign user to dynamic groups based on their role and location"""
    if role == "student" and institution and city:
        group_name = f"Students in {city} at {institution}"
    elif role == "tutor" and city:
        group_name = f"Tutors in {city}"
    elif role == "service provider" and city:
        group_name = f"Service Providers in {city}"
    elif role == "jobseeker" and city:
        group_name = f"Jobseekers in {city}"
    elif role == "hs student" and city:
        group_name = f"High School Students in {city}"
    else:
        group_name = f"{role.title()}s in {city}" 

    # Create Django auth group (for permissions)
    auth_group, _ = Group.objects.get_or_create(name=group_name)
    user.groups.add(auth_group)
    
    # Create or get corresponding GroupChat
    group_chat, created = GroupChat.objects.get_or_create(
        name=group_name,
        city=city,
        institution=institution if role == "student" else "",
        defaults={
            'created_by': user,
            'is_dynamic': True,  # Add this field to your model to mark dynamic groups
        }
    )
    
    # Add user to the group chat
    group_chat.members.add(user)
    
    # Create corresponding ChatRoom for WebSocket functionality
    chat_room, created = ChatRoom.objects.get_or_create(
        id=group_chat.id,
        defaults={'name': group_name}
    )
    chat_room.members.add(user)
    
    return group_chat


def get_user_role_and_details(user):
    """Get user's role and relevant details for group suggestions"""
    profile, profile_type = get_user_profile(user)
    
    if not profile:
        return None, None, None, None
    
    city = getattr(profile, 'city', None)
    institution = None
    role = None
    
    if profile_type == 'student_profile':
        role = 'student'
        institution = getattr(profile, 'institution', None)
    elif profile_type == 'tutor_profile':
        role = 'tutor'
    elif profile_type == 'serviceprovider_profile':
        role = 'service provider'
    elif profile_type == 'jobseeker_profile':
        role = 'jobseeker'
    elif profile_type == 'hstudent_profile':
        role = 'hs student'
        institution = getattr(profile, 'schoolName', None)
    
    return role, city, institution, profile


class CreateGroupView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        name = request.data.get("name")
        city = request.data.get("city")
        institution = request.data.get("institution", "")
        hobbies = request.data.get("hobbies", [])

        if not name or not city:
            return Response({"error": "Name and city are required."}, status=status.HTTP_400_BAD_REQUEST)

        group = GroupChat.objects.create(
            name=name,
            city=city,
            institution=institution,
            created_by=request.user,
            is_dynamic=False  # User-created groups are not dynamic
        )
        group.members.add(request.user)
        group.hobbies.set(hobbies)

        # Create corresponding ChatRoom for WebSocket functionality
        chat_room, created = ChatRoom.objects.get_or_create(
            id=group.id,
            defaults={'name': name}
        )
        chat_room.members.add(request.user)
        
        return Response(GroupChatSerializer(group).data, status=status.HTTP_201_CREATED)


class GroupListCreate(generics.ListCreateAPIView):
    queryset = GroupChat.objects.all()
    
    def get_serializer_class(self):
        if self.request.method == 'POST':
            return GroupCreateSerializer
        return GroupChatSerializer

    def perform_create(self, serializer):
        group = serializer.save(admin=self.request.user, is_dynamic=False)
        
        # Create corresponding ChatRoom
        chat_room, created = ChatRoom.objects.get_or_create(
            id=group.id,
            defaults={'name': group.name}
        )
        chat_room.members.add(self.request.user)


class JoinGroupView(APIView):
    permission_classes = [AllowAny]

    def post(self, request, group_id):
        try:
            group = GroupChat.objects.get(id=group_id)
            group.members.add(request.user)
            
            # Ensure ChatRoom exists for this group
            chat_room, created = ChatRoom.objects.get_or_create(
                id=group_id,
                defaults={'name': group.name}
            )
            chat_room.members.add(request.user)
            
            return Response({"message": "Joined group successfully."}, status=status.HTTP_200_OK)
        except GroupChat.DoesNotExist:
            return Response({"error": "Group not found."}, status=status.HTTP_404_NOT_FOUND)
        
class UnifiedGroupCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        name = request.data.get("name")
        description = request.data.get("description", "")
        is_private = request.data.get("is_private", False)
        city = request.data.get("city")
        institution = request.data.get("institution", "")
        hobbies = request.data.get("hobbies", [])

        if not name:
            return Response({"error": "Name is required."}, status=status.HTTP_400_BAD_REQUEST)

        # Get user's profile data if city/institution not provided
        if not city:
            try:
                role, user_city, user_institution, profile = get_user_role_and_details(request.user)
                city = user_city or ""
                if not institution:
                    institution = user_institution or ""
            except:
                city = ""

        try:
            with transaction.atomic():
                # Create the group
                group = GroupChat.objects.create(
                    name=name,
                    description=description,
                    city=city,
                    institution=institution,
                    is_dynamic=False  # User-created groups are not dynamic
                )
                
                # Add creator as member
                group.members.add(request.user)
                
                # Set hobbies if provided
                if hobbies:
                    if isinstance(hobbies[0], str):
                        # If hobbies are strings, find or create hobby objects
                        from ..models import Hobby  
                        hobby_objects = []
                        for hobby_name in hobbies:
                            hobby, created = Hobby.objects.get_or_create(name=hobby_name)
                            hobby_objects.append(hobby)
                        group.hobbies.set(hobby_objects)
                    else:
                        # If hobbies are IDs
                        group.hobbies.set(hobbies)

                # Create corresponding ChatRoom for WebSocket functionality
                chat_room, created = ChatRoom.objects.get_or_create(
                    id=group.id,
                    defaults={'name': name}
                )
                chat_room.members.add(request.user)
                
                return Response(GroupChatSerializer(group).data, status=status.HTTP_201_CREATED)
                
        except Exception as e:
            return Response(
                {"error": f"Failed to create group: {str(e)}"}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class LeaveGroupView(APIView):
    permission_classes = [AllowAny]

    def post(self, request, group_id):
        try:
            group = GroupChat.objects.get(id=group_id)
            group.members.remove(request.user)
            
            # Also remove from ChatRoom
            try:
                chat_room = ChatRoom.objects.get(id=group_id)
                chat_room.members.remove(request.user)
            except ChatRoom.DoesNotExist:
                pass
            
            return Response({"message": "Left group successfully."}, status=status.HTTP_200_OK)
        except GroupChat.DoesNotExist:
            return Response({"error": "Group not found."}, status=status.HTTP_404_NOT_FOUND)


class InstitutionGroupsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        role, city, institution, profile = get_user_role_and_details(request.user)
        
        if not institution:
            return Response([], status=status.HTTP_200_OK)

        # Get both user-created and dynamic groups for the institution
        groups = GroupChat.objects.filter(
            Q(institution=institution) | 
            Q(name__icontains=institution, city=city)
        ).distinct()
        
        serializer = GroupChatSerializer(groups, many=True)
        return Response(serializer.data)


class CityHobbyGroupsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        role, city, institution, profile = get_user_role_and_details(request.user)
        
        if not profile or not city:
            return Response([], status=status.HTTP_200_OK)
        
        user_hobbies = get_user_hobbies(profile)
        
        if not user_hobbies:
            # Return city-based groups even without hobbies
            groups = GroupChat.objects.filter(city=city).distinct()
        else:
            # Filter by both city and hobbies
            if isinstance(user_hobbies[0], str):
                groups = GroupChat.objects.filter(
                    city=city, 
                    hobbies__name__in=user_hobbies
                ).distinct()
            else:
                groups = GroupChat.objects.filter(
                    city=city, 
                    hobbies__in=user_hobbies
                ).distinct()
        
        return Response(GroupChatSerializer(groups, many=True).data)


class GroupSuggestionsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        role, city, institution, profile = get_user_role_and_details(request.user)
        
        if not profile:
            return Response([], status=status.HTTP_200_OK)
        
        user_hobbies = get_user_hobbies(profile)
        
        # Get groups user is not already a member of
        user_groups = GroupChat.objects.filter(members=request.user)
        available_groups = GroupChat.objects.exclude(id__in=user_groups.values_list("id", flat=True))
        
        suggestions = []
        
        for group in available_groups:
            score = 0
            
            # Higher score for groups in the same city
            if city and group.city == city:
                score += 10
            
            # Higher score for groups at the same institution
            if institution and group.institution == institution:
                score += 15
            
            # Score based on matching hobbies
            if user_hobbies:
                group_hobbies = list(group.hobbies.all())
                
                if group_hobbies:
                    if isinstance(user_hobbies[0], str) and hasattr(group_hobbies[0], 'name'):
                        group_hobby_names = [h.name for h in group_hobbies]
                        common_hobbies = set(user_hobbies) & set(group_hobby_names)
                    elif hasattr(user_hobbies[0], 'name') and isinstance(group_hobbies[0], str):
                        user_hobby_names = [h.name for h in user_hobbies]
                        common_hobbies = set(user_hobby_names) & set(group_hobbies)
                    elif isinstance(user_hobbies[0], str) and isinstance(group_hobbies[0], str):
                        common_hobbies = set(user_hobbies) & set(group_hobbies)
                    else:
                        common_hobbies = set(user_hobbies) & set(group_hobbies)
                    
                    score += len(common_hobbies) * 5
            
            # Bonus for dynamic groups that match user's role
            if hasattr(group, 'is_dynamic') and group.is_dynamic:
                if role and role.lower() in group.name.lower():
                    score += 20
            
            # Small score based on group popularity (but don't let it dominate)
            member_count = group.members.count()
            if member_count > 0:
                score += min(member_count * 0.1, 2)  # Cap at 2 points for popularity
            
            # Only include groups with some relevance (score > 0)
            if score > 0:
                suggestions.append((group, score))
        
        # Sort by score and take top 15 for better variety
        suggestions.sort(key=lambda x: x[1], reverse=True)
        top_groups = [group for group, score in suggestions[:15]]
        
        serialized = GroupChatSerializer(top_groups, many=True)
        return Response(serialized.data, status=status.HTTP_200_OK)


class JoinedGroupsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user_groups = request.user.groups_chats.all()
        return Response(GroupChatSerializer(user_groups, many=True).data)


class JoinableGroupsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        joinable = GroupChat.objects.exclude(members=request.user)
        return Response(GroupChatSerializer(joinable, many=True).data)


class DynamicGroupsView(APIView):
    """View to get all dynamic groups for the current user's profile"""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        role, city, institution, profile = get_user_role_and_details(request.user)
        
        if not role or not city:
            return Response([], status=status.HTTP_200_OK)
        
        # Filter dynamic groups based on user's role and location
        dynamic_groups = GroupChat.objects.filter(
            is_dynamic=True,
            city=city
        )
        
        # Further filter based on role-specific criteria
        if role == 'student' and institution:
            dynamic_groups = dynamic_groups.filter(
                Q(institution=institution) | Q(name__icontains="Students")
            )
        elif role in ['tutor', 'service provider', 'jobseeker', 'hs student']:
            role_keyword = role.replace(' ', ' ').title()
            dynamic_groups = dynamic_groups.filter(name__icontains=role_keyword)
        
        return Response(GroupChatSerializer(dynamic_groups, many=True).data)


