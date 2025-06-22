from rest_framework import serializers
from ..models import StudentProfile, CustomUser
from .authentication import UserSerializer

class StudentProfileSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)
    
    class Meta:
        model = StudentProfile
        fields = '__all__'
        extra_kwargs = {
            'user': {'read_only': True},
            'profile_picture': {'required': False, 'allow_null': True},
        }

    def validate_year_of_study(self, value):
        if value is not None and (value < 1 or value > 6):
            raise serializers.ValidationError("Year of study must be between 1 and 6")
        return value

class StudentProfileUpdateSerializer(serializers.ModelSerializer):
    year_of_study = serializers.IntegerField(required=False, allow_null=True)
    hobbies = serializers.ListField(
        child=serializers.CharField(),
        required=False,
        allow_empty=True
    )

    class Meta:
        model = StudentProfile
        fields = [
            'year_of_study', 'course', 'hobbies', 'qualification', 
            'bio', 'profile_picture', 'institution', 'city'
        ]
        extra_kwargs = {
            'profile_picture': {'required': False, 'allow_null': True},
            'course': {'required': False, 'allow_blank': True},
            'institution': {'required': False, 'allow_blank': True},
            'qualification': {'required': False, 'allow_blank': True},
            'bio': {'required': False, 'allow_blank': True},
            'city': {'required': False, 'allow_blank': True},
        }

    def validate_year_of_study(self, value):
        if value is not None and (value < 1 or value > 6):
            raise serializers.ValidationError("Year of study must be between 1 and 6")
        return value
    


