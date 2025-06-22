from rest_framework import serializers
from django.db import models

from ..models.authentication import ConnectionRequest
from .tutoring import SubjectSerializer
from ..models import CustomUser, StudentProfile, TutorProfile, HStudents, ServiceProvider,JobSeeker

class UserSerializer(serializers.ModelSerializer):
    mutual_connections = serializers.SerializerMethodField()
    profile_picture_url = serializers.SerializerMethodField()

    class Meta:
        model = CustomUser
        fields = (
            'id', 'username', 'email', 'password', 'bio',
            'roles', 'active_role', 'city', 'profile_picture', 'profile_picture_url', 
            'hobbies', 'mutual_connections'
        )
        extra_kwargs = {
            'password': {'write_only': True},
            'roles': {'required': False},
            'active_role': {'required': False},
            'city': {'required': False},
            'bio': {'required': False},
            'hobbies': {'required': False},
            'profile_picture': {'required': False},
        }

    def get_profile_picture_url(self, obj):
        """Get full URL for profile picture"""
        if obj.profile_picture:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.profile_picture.url)
            return obj.profile_picture.url
        return None

    def get_mutual_connections(self, obj):
        # Return 0 if no context or request user available
        request = self.context.get('request')
        if not request or not request.user.is_authenticated:
            return 0
            
        # Calculate mutual connections logic here
        # For now, return 0 - you can implement the logic later
        return 0
        
    def create(self, validated_data):
        # Create a new user with a hashed password
        password = validated_data.pop('password', None)
        user = CustomUser.objects.create(**validated_data)
        if password:
            user.set_password(password)
            user.save()
        return user
    
    def update(self, instance, validated_data):
        # Handle password separately if provided
        password = validated_data.pop('password', None)
        
        # Update all other fields
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        
        # Hash and set password if provided
        if password:
            instance.set_password(password)
        
        instance.save()
        return instance
    
class PublicUserSerializer(serializers.ModelSerializer):
    """Serializer for public user profile (limited fields)"""
    profile_picture_url = serializers.SerializerMethodField()
    
    class Meta:
        model = CustomUser
        fields = (
            'id', 'username', 'first_name', 'last_name',
            'profile_picture_url', 'bio', 'city', 'active_role',
            'date_joined'
        )
    
    def get_profile_picture_url(self, obj):
        """Get full URL for profile picture"""
        if obj.profile_picture:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.profile_picture.url)
            return obj.profile_picture.url
        return None
   

class StudentProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = StudentProfile
        exclude = ('user',)
        extra_kwargs = {
            'profile_picture': {'required': False},
            'bio': {'required': False},
        }

class TutorProfileSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)
    subjects = SubjectSerializer(many=True, read_only=True) 
    # Add computed fields for compatibility with your Flutter app
    total_students = serializers.SerializerMethodField()
    total_hours = serializers.SerializerMethodField()
    average_rating = serializers.SerializerMethodField()

    class Meta:
        model = TutorProfile
        fields = [
            'id', 'user', 'place', 'city', 'phone_number', 'hourly_rate',
            'address', 'is_available_online', 'is_available_physical',
            'rating', 'total_reviews', 'cv', 'bio', 'profile_picture',
            'subjects', 'total_students', 'total_hours', 'average_rating'
        ]

    def get_total_students(self, obj):
        # Count unique students from bookings
        from ..models import Booking
        return Booking.objects.filter(tutor=obj).values('student').distinct().count()

    def get_total_hours(self, obj):
        # Sum total hours from completed bookings
        from ..models import Booking
        from django.db.models import Sum
        total_minutes = Booking.objects.filter(
            tutor=obj, 
            status='completed'
        ).aggregate(Sum('duration'))['duration__sum'] or 0
        return total_minutes // 60  # Convert minutes to hours

    def get_average_rating(self, obj):
        # Return the rating field (you might want to calculate from reviews instead)
        return float(obj.rating)

class HStudentProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = HStudents
        exclude = ('user',)
        extra_kwargs = {
            'profile_picture': {'required': False},
            'bio': {'required': False},
        }

class ServiceProviderSerializer(serializers.ModelSerializer):
    class Meta:
        model = ServiceProvider
        exclude = ('user',)
        extra_kwargs = {
            'profile_picture': {'required': False},
            'bio': {'required': False},
        }

class JobSeekerSerializer(serializers.ModelSerializer):
    class Meta:
        model = JobSeeker
        exclude = ('user',)
        extra_kwargs = {
            'profile_picture': {'required': False},
            'bio': {'required': False},
        }

class UserRegistrationSerializer(serializers.Serializer):
    role = serializers.CharField(required=True)
    # Common fields
    # Student fields
    year_of_study = serializers.IntegerField(required=False)
    course = serializers.CharField(required=False)
    hobbies = serializers.CharField(required=False)
    qualification = serializers.CharField(required=False)
    institution = serializers.CharField(required=False)
    # Tutor fields
    about = serializers.CharField(required=False)
    phone_number = serializers.IntegerField(required=False)
    hourly_rate = serializers.DecimalField(max_digits=10, decimal_places=2, required=False)
    qualifications = serializers.CharField(required=False)
    # Service Provider fields
    company_name = serializers.CharField(required=False)
    description = serializers.CharField(required=False)
    typeofservice = serializers.CharField(required=False)
    interests = serializers.CharField(required=False)

class UserBasicSerializer(serializers.ModelSerializer):
    """Basic user info for connections and messaging"""
    class Meta:
        model = CustomUser
        fields = ['id', 'username', 'first_name', 'last_name', 'email']

class ConnectionRequestSerializer(serializers.ModelSerializer):
    from_user = UserSerializer(read_only=True)
    to_user = UserSerializer(read_only=True)
    
    class Meta:
        model = ConnectionRequest
        fields = ['id', 'from_user', 'to_user', 'status', 'created_at']
        
    def to_representation(self, instance):
        """Ensure no null values in serialized data"""
        data = super().to_representation(instance)
        
        # Ensure required fields are never null
        if data.get('from_user') is None:
            data['from_user'] = {
                'id': 0,
                'username': 'Unknown',
                'first_name': None,
                'last_name': None,
                'profile_picture': None,
                'bio': None,
                'mutual_connections': 0
            }
            
        if data.get('to_user') is None:
            data['to_user'] = {
                'id': 0,
                'username': 'Unknown',
                'first_name': None,
                'last_name': None,
                'profile_picture': None,
                'bio': None,
                'mutual_connections': 0
            }
            
        return data