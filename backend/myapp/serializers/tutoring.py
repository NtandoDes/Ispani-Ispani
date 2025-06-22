from rest_framework import serializers

from ..models.authentication import CustomUser
from ..models.tutoring import  Subject, Review, Booking, TutorAvailability
from ..models import TutorProfile, StudentProfile

class TutorProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = TutorProfile
        fields = '__all__'

class StudentProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = StudentProfile
        fields = '__all__'

class BookingSerializer(serializers.ModelSerializer):
    # Remove the source mapping since we're using 'platform' directly now
    # Use IntegerField for IDs instead of object fields
    tutor_id = serializers.IntegerField(write_only=True)
    subject_id = serializers.IntegerField(write_only=True)
    student_id = serializers.IntegerField(write_only=True, required=False)
    
    # Read-only fields for response
    tutor_name = serializers.CharField(source='tutor.username', read_only=True)
    student_name = serializers.CharField(source='student.username', read_only=True)
    subject_name = serializers.CharField(source='subject.name', read_only=True)
    
    class Meta:
        model = Booking
        fields = [
            'id', 'tutor_id', 'subject_id', 'student_id',
            'tutor', 'student', 'subject',  # Keep these for read operations
            'tutor_name', 'student_name', 'subject_name',  # Display names
            'date', 'start_time', 'end_time', 'platform', 'notes',  # Now using 'platform' directly
            'booking_type', 'status', 'total_cost', 'hourly_rate',
            'meeting_link', 'created_at', 'confirmed_at', 'completed_at'
        ]
        read_only_fields = [
            'id', 'tutor', 'student', 'subject', 'total_cost', 
            'meeting_link', 'created_at', 'confirmed_at', 'completed_at',
            'tutor_name', 'student_name', 'subject_name'
        ]
    
    def create(self, validated_data):
        """Override create to handle the field mappings properly"""
        # Extract the IDs for foreign key relationships
        tutor_id = validated_data.pop('tutor_id', None)
        subject_id = validated_data.pop('subject_id', None)
        student_id = validated_data.pop('student_id', None)
        
        # Get the actual objects
        if tutor_id:
            validated_data['tutor'] = CustomUser.objects.get(id=tutor_id)
        if subject_id:
            validated_data['subject'] = Subject.objects.get(id=subject_id)
        if student_id:
            validated_data['student'] = CustomUser.objects.get(id=student_id)
        
        return super().create(validated_data)
    
    def validate_tutor_id(self, value):
        """Validate that the tutor exists and has a tutor profile"""
        try:
            user = CustomUser.objects.get(id=value)
            if not hasattr(user, 'tutor_profile'):
                raise serializers.ValidationError("User is not a tutor")
            return value
        except CustomUser.DoesNotExist:
            raise serializers.ValidationError("Tutor not found")
    
    def validate_subject_id(self, value):
        """Validate that the subject exists"""
        try:
            Subject.objects.get(id=value)
            return value
        except Subject.DoesNotExist:
            raise serializers.ValidationError("Subject not found")
    
    def validate_student_id(self, value):
        """Validate that the student exists (if provided)"""
        if value:
            try:
                user = CustomUser.objects.get(id=value)
                if not hasattr(user, 'student_profile'):
                    raise serializers.ValidationError("User is not a student")
                return value
            except CustomUser.DoesNotExist:
                raise serializers.ValidationError("Student not found")
        return value

class ReviewSerializer(serializers.ModelSerializer):
    class Meta:
        model = Review
        fields = '__all__'

class SubjectSerializer(serializers.ModelSerializer):
    class Meta:
        model = Subject
        fields = ['id', 'name', 'description']

class TutorAvailabilitySerializer(serializers.ModelSerializer):
    class Meta:
        model = TutorAvailability
        fields = ['id', 'tutor', 'day_of_week', 'start_time', 'end_time', 'is_available']