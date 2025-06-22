from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from ..models import StudentProfile, CustomUser
from ..serializers.student import StudentProfileSerializer, StudentProfileUpdateSerializer

class StudentProfileView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            student_profile = request.user.student_profile
            serializer = StudentProfileSerializer(student_profile)
            return Response(serializer.data)
        except StudentProfile.DoesNotExist:
            return Response(
                {"error": "Student profile not found"}, 
                status=status.HTTP_404_NOT_FOUND
            )

class StudentProfileUpdateView(APIView):
    permission_classes = [IsAuthenticated]

    def get_object(self, user):
        try:
            return user.student_profile
        except StudentProfile.DoesNotExist:
            return None

    def get(self, request):
        student_profile = self.get_object(request.user)
        if not student_profile:
            return Response(
                {"error": "Student profile not found"}, 
                status=status.HTTP_404_NOT_FOUND
            )
        serializer = StudentProfileUpdateSerializer(student_profile)
        return Response(serializer.data)

    def put(self, request):
        student_profile = self.get_object(request.user)
        if not student_profile:
            return Response(
                {"error": "Student profile not found"}, 
                status=status.HTTP_404_NOT_FOUND
            )

        serializer = StudentProfileUpdateSerializer(
            student_profile, 
            data=request.data,
            partial=True
        )
        
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def patch(self, request):
        # For partial updates
        return self.put(request)