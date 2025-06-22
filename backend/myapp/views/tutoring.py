from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView
from django.contrib.auth import authenticate
from django.db.models import Q, Avg
from django.utils import timezone
from datetime import datetime, time, timedelta
from django.shortcuts import get_object_or_404
from rest_framework import serializers as drf_serializers

from ..models.tutoring  import CustomUser, TutorProfile, StudentProfile, Subject, Booking, TutorAvailability, Review
from ..serializers.tutoring import (
    TutorProfileSerializer, StudentProfileSerializer, SubjectSerializer,
    BookingSerializer, ReviewSerializer
)

class TutorViewSet(viewsets.ModelViewSet):
    queryset = TutorProfile.objects.select_related('user').prefetch_related('subjects').all()
    serializer_class = TutorProfileSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        queryset = super().get_queryset()
        subject = self.request.query_params.get('subject')
        booking_type = self.request.query_params.get('booking_type')
        
        if subject and subject != 'All':
            queryset = queryset.filter(subjects__name__icontains=subject)
        
        if booking_type == 'online':
            queryset = queryset.filter(is_available_online=True)
        elif booking_type == 'physical':
            queryset = queryset.filter(is_available_physical=True)
        
        return queryset.distinct()

    @action(detail=False, methods=['get'])
    def my_earnings(self, request):
        """Get earnings for the authenticated tutor"""
        if not hasattr(request.user, 'tutor_profile'):
            return Response({'error': 'User is not a tutor'}, status=status.HTTP_403_FORBIDDEN)
        
        tutor = request.user.tutor_profile
        completed_bookings = Booking.objects.filter(tutor=tutor, status='completed')
        
        total_earnings = sum(booking.total_cost or 0 for booking in completed_bookings)
        total_hours = completed_bookings.count()  # Simplified calculation
        
        return Response({
            'total_earnings': total_earnings,
            'total_hours': total_hours,
            'completed_bookings': completed_bookings.count()
        })

class StudentViewSet(viewsets.ModelViewSet):
    queryset = StudentProfile.objects.all()
    serializer_class = StudentProfileSerializer
    permission_classes = [permissions.IsAuthenticated]

    @action(detail=True, methods=['get'])
    def bookings(self, request, pk=None):
        student = self.get_object()
        bookings = Booking.objects.filter(student=student)
        serializer = BookingSerializer(bookings, many=True)
        return Response(serializer.data)

class SubjectViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Subject.objects.all()
    serializer_class = SubjectSerializer
    permission_classes = [permissions.IsAuthenticated]

class BookingViewSet(viewsets.ModelViewSet):
    queryset = Booking.objects.all()
    serializer_class = BookingSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        queryset = super().get_queryset()
        user = self.request.user
        
        # Check for specific user ID parameter from frontend
        user_id = self.request.query_params.get('user_id')
        student_id = self.request.query_params.get('student_id')
        tutor_id = self.request.query_params.get('tutor_id')
        
        # If specific IDs are provided, use them
        if student_id:
            try:
                student_profile = StudentProfile.objects.get(user=student_id)
                # Assuming student field in Booking is a ForeignKey to StudentProfile
                queryset = queryset.filter(student=student_profile)
            except StudentProfile.DoesNotExist:
                return queryset.none()
        elif tutor_id:
            try:
                # FIXED: Look up by user_id since TutorProfile doesn't have 'id' field
                tutor_profile = TutorProfile.objects.get(user_id=tutor_id)
                # Filter by the user who owns this tutor profile
                queryset = queryset.filter(tutor=tutor_profile.user)
            except TutorProfile.DoesNotExist:
                return queryset.none()
        elif user_id:
            try:
                target_user = CustomUser.objects.get(id=user_id)
                # Filter based on what profile the user has
                if hasattr(target_user, 'tutor_profile'):
                    queryset = queryset.filter(tutor=target_user)
                elif hasattr(target_user, 'student_profile'):
                    # Assuming student field expects the user, not the profile
                    queryset = queryset.filter(student=target_user)
                else:
                    return queryset.none()
            except CustomUser.DoesNotExist:
                return queryset.none()
        else:
            # Default behavior: Filter bookings based on current user type
            if hasattr(user, 'tutor_profile'):
                # Filter by the user, not the tutor_profile
                queryset = queryset.filter(tutor=user)
            elif hasattr(user, 'student_profile'):
                # Filter by the user, not the student_profile
                queryset = queryset.filter(student=user)
            else:
                # If user has no profile, return empty queryset
                return queryset.none()
        
        # Additional filters
        status_filter = self.request.query_params.get('status')
        date_filter = self.request.query_params.get('date')
        
        if status_filter:
            queryset = queryset.filter(status=status_filter)
        if date_filter:
            queryset = queryset.filter(date=date_filter)
        
        return queryset

    def perform_create(self, serializer):
        """Handle booking creation with flexible student assignment"""
        # Check if student_id is provided in the request data
        student_id = self.request.data.get('student_id')
        tutor_id = self.request.data.get('tutor_id')  # This is the tutor USER ID or PROFILE ID
        subject_id = self.request.data.get('subject_id')
        
        # Get student
        if student_id:
            try:
                student_profile = StudentProfile.objects.get(user=student_id)
                # Get the user associated with this student profile
                student_user = student_profile.user
            except StudentProfile.DoesNotExist:
                if hasattr(self.request.user, 'student_profile'):
                    student_user = self.request.user
                else:
                    raise drf_serializers.ValidationError("Invalid student_id provided and user has no student profile")
        else:
            if hasattr(self.request.user, 'student_profile'):
                student_user = self.request.user
            else:
                raise drf_serializers.ValidationError("User must have a student profile to create bookings")
        
        # Get tutor and subject
        try:
            # FIXED: Try different ways to get the tutor profile
            tutor_profile = None
            tutor_user = None
            
            # Option 1: Try to get by user_id (if tutor_id is the user ID)
            try:
                tutor_profile = TutorProfile.objects.get(user_id=tutor_id)
                tutor_user = tutor_profile.user
            except TutorProfile.DoesNotExist:
                # Option 2: Try to get by user (if tutor_id is the user ID directly)
                try:
                    user_obj = CustomUser.objects.get(id=tutor_id)
                    tutor_profile = user_obj.tutor_profile
                    tutor_user = user_obj
                except (CustomUser.DoesNotExist, AttributeError):
                    raise drf_serializers.ValidationError("Invalid tutor_id - tutor profile not found")
            
            subject = Subject.objects.get(id=subject_id)
        except Subject.DoesNotExist:
            raise drf_serializers.ValidationError("Invalid subject_id")
        
        # Calculate total cost - FIXED: Handle missing end_time
        start_time_str = self.request.data.get('start_time')
        end_time_str = self.request.data.get('end_time')
        
        if start_time_str and end_time_str:
            try:
                start_time = datetime.strptime(start_time_str, '%H:%M').time()
                end_time = datetime.strptime(end_time_str, '%H:%M').time()
                
                # Calculate duration in hours
                duration_hours = (datetime.combine(datetime.min, end_time) - datetime.combine(datetime.min, start_time)).seconds / 3600
                total_cost = duration_hours * float(tutor_profile.hourly_rate)
            except ValueError:
                # If time parsing fails, default to 1 hour
                total_cost = float(tutor_profile.hourly_rate)
        else:
            # If no end_time provided, assume 1 hour session
            total_cost = float(tutor_profile.hourly_rate)
        
        # Get additional fields from request
        platform = self.request.data.get('platform', '')
        notes = self.request.data.get('notes', '')
        booking_date = self.request.data.get('date')
        booking_type = self.request.data.get('booking_type', 'online')
        hourly_rate = self.request.data.get('hourly_rate', tutor_profile.hourly_rate)
        
        # Parse date
        if booking_date:
            try:
                if isinstance(booking_date, str):
                    booking_date = datetime.strptime(booking_date, '%Y-%m-%d').date()
            except ValueError:
                raise drf_serializers.ValidationError("Invalid date format. Use YYYY-MM-DD")
        
        # Parse start time
        start_time_obj = None
        if start_time_str:
            try:
                start_time_obj = datetime.strptime(start_time_str, '%H:%M').time()
            except ValueError:
                raise drf_serializers.ValidationError("Invalid start_time format. Use HH:MM")
        
        serializer.save(
            student=student_user,
            tutor=tutor_user,
            subject=subject,
            total_cost=total_cost,
            platform=platform,
            notes=notes,
            date=booking_date,
            start_time=start_time_obj,
            booking_type=booking_type,
            hourly_rate=hourly_rate,
            status='pending'
        )
        
    @action(detail=True, methods=['post'])
    def confirm(self, request, pk=None):
        booking = self.get_object()
        if booking.status == 'pending':
            booking.status = 'confirmed'
            booking.confirmed_at = timezone.now()
            
            # Generate meeting link for online bookings
            if booking.booking_type == 'online' and not booking.meeting_link:
                booking.meeting_link = f"https://example.com/meeting/{booking.id}"
            
            booking.save()
            serializer = self.get_serializer(booking)
            return Response(serializer.data)
        
        return Response(
            {'error': 'Booking cannot be confirmed'}, 
            status=status.HTTP_400_BAD_REQUEST
        )

    @action(detail=True, methods=['post'])
    def cancel(self, request, pk=None):
        booking = self.get_object()
        if booking.status in ['pending', 'confirmed']:
            booking.status = 'cancelled'
            booking.cancelled_at = timezone.now()
            booking.save()
            serializer = self.get_serializer(booking)
            return Response(serializer.data)
        
        return Response(
            {'error': 'Booking cannot be cancelled'}, 
            status=status.HTTP_400_BAD_REQUEST
        )

    @action(detail=True, methods=['post'])
    def complete(self, request, pk=None):
        booking = self.get_object()
        if booking.status == 'confirmed':
            booking.status = 'completed'
            booking.completed_at = timezone.now()
            booking.save()
            serializer = self.get_serializer(booking)
            return Response(serializer.data)
        
        return Response(
            {'error': 'Booking cannot be completed'}, 
            status=status.HTTP_400_BAD_REQUEST
        )
    
    @action(detail=True, methods=['post'])
    def reschedule(self, request, pk=None):
        """Reschedule a booking to a new date and time"""
        try:
            booking = self.get_object()
        except Booking.DoesNotExist:
            return Response(
                {'error': 'Booking not found'}, 
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Only allow rescheduling for pending or confirmed bookings
        if booking.status not in ['pending', 'confirmed']:
            return Response(
                {'error': 'Only pending or confirmed bookings can be rescheduled'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Get new date and time from request
        new_date = request.data.get('date')
        new_start_time = request.data.get('start_time')
        new_end_time = request.data.get('end_time')
        reschedule_reason = request.data.get('reason', '')
        
        # Validate required fields
        if not new_date:
            return Response(
                {'error': 'New date is required'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        if not new_start_time:
            return Response(
                {'error': 'New start time is required'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Parse and validate new date
        try:
            if isinstance(new_date, str):
                new_date_obj = datetime.strptime(new_date, '%Y-%m-%d').date()
            else:
                new_date_obj = new_date
                
            # Check if new date is not in the past
            if new_date_obj <= timezone.now().date():
                return Response(
                    {'error': 'Cannot reschedule to today or a past date'}, 
                    status=status.HTTP_400_BAD_REQUEST
                )
        except ValueError:
            return Response(
                {'error': 'Invalid date format. Use YYYY-MM-DD'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Parse and validate new start time
        try:
            new_start_time_obj = datetime.strptime(new_start_time, '%H:%M').time()
        except ValueError:
            return Response(
                {'error': 'Invalid start time format. Use HH:MM'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Parse end time if provided and recalculate cost
        new_end_time_obj = None
        new_total_cost = booking.total_cost  # Default to existing cost
        
        if new_end_time:
            try:
                new_end_time_obj = datetime.strptime(new_end_time, '%H:%M').time()
                
                # Validate that end time is after start time
                start_datetime = datetime.combine(datetime.min, new_start_time_obj)
                end_datetime = datetime.combine(datetime.min, new_end_time_obj)
                
                if end_datetime <= start_datetime:
                    return Response(
                        {'error': 'End time must be after start time'}, 
                        status=status.HTTP_400_BAD_REQUEST
                    )
                
                # Calculate new duration and cost
                duration_hours = (end_datetime - start_datetime).seconds / 3600
                
                # Get tutor profile to calculate new cost
                try:
                    if hasattr(booking.tutor, 'tutor_profile'):
                        tutor_profile = booking.tutor.tutor_profile
                        new_total_cost = duration_hours * float(tutor_profile.hourly_rate)
                    else:
                        # Try to get tutor profile by user_id
                        try:
                            tutor_profile = TutorProfile.objects.get(user=booking.tutor)
                            new_total_cost = duration_hours * float(tutor_profile.hourly_rate)
                        except TutorProfile.DoesNotExist:
                            # Keep existing cost if tutor profile not found
                            pass
                except (AttributeError, ValueError):
                    # Keep existing cost if calculation fails
                    pass
                    
            except ValueError:
                return Response(
                    {'error': 'Invalid end time format. Use HH:MM'}, 
                    status=status.HTTP_400_BAD_REQUEST
                )
        
        # Check for scheduling conflicts with the tutor
        conflicting_bookings = Booking.objects.filter(
            tutor=booking.tutor,
            date=new_date_obj,
            start_time=new_start_time_obj,
            status__in=['pending', 'confirmed']
        ).exclude(id=booking.id)
        
        if conflicting_bookings.exists():
            return Response(
                {'error': 'The tutor already has a booking at this time'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Additional validation: Check if the new time is during reasonable hours
        if new_start_time_obj.hour < 6 or new_start_time_obj.hour > 22:
            return Response(
                {'error': 'Please select a time between 6:00 AM and 10:00 PM'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Store original booking details for history/audit
        original_date = booking.date
        original_start_time = booking.start_time
        original_end_time = getattr(booking, 'end_time', None)
        original_total_cost = booking.total_cost
        
        try:
            # Update booking with new details
            booking.date = new_date_obj
            booking.start_time = new_start_time_obj
            
            if new_end_time_obj:
                booking.end_time = new_end_time_obj
                booking.total_cost = new_total_cost
            
            # Add reschedule information
            booking.rescheduled_at = timezone.now()
            booking.reschedule_reason = reschedule_reason
            
            # Reset status to pending if it was confirmed (tutor needs to reconfirm)
            if booking.status == 'confirmed':
                booking.status = 'pending'
                booking.confirmed_at = None
                # Clear meeting link if it exists, as it might need to be regenerated
                booking.meeting_link = ''
            
            # Save the updated booking
            booking.save()
            
            # You might want to send notifications here
            # send_reschedule_notification(booking, original_date, original_start_time)
            
        except Exception as e:
            return Response(
                {'error': f'Failed to update booking: {str(e)}'}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
        
        # Serialize the updated booking
        serializer = self.get_serializer(booking)
        
        # Prepare response with reschedule information
        response_data = serializer.data
        response_data['reschedule_info'] = {
            'original_date': original_date.strftime('%Y-%m-%d') if original_date else None,
            'original_start_time': original_start_time.strftime('%H:%M') if original_start_time else None,
            'original_end_time': original_end_time.strftime('%H:%M') if original_end_time else None,
            'original_total_cost': float(original_total_cost) if original_total_cost else None,
            'new_date': new_date_obj.strftime('%Y-%m-%d'),
            'new_start_time': new_start_time_obj.strftime('%H:%M'),
            'new_end_time': new_end_time_obj.strftime('%H:%M') if new_end_time_obj else None,
            'new_total_cost': float(new_total_cost) if new_total_cost else None,
            'rescheduled_at': booking.rescheduled_at.isoformat(),
            'reason': reschedule_reason,
            'status_changed': 'Booking status reset to pending - tutor needs to reconfirm' if booking.status == 'pending' else None
        }
        
        return Response(response_data, status=status.HTTP_200_OK)

    @action(detail=False, methods=['get'])
    def calendar(self, request):
        """Get bookings for calendar view"""
        user = request.user
        start_date = request.query_params.get('start_date', timezone.now().date())
        end_date = request.query_params.get('end_date', timezone.now().date() + timedelta(days=14))
        
        # Check for user_id parameter for flexibility
        user_id = request.query_params.get('user_id')
        if user_id:
            try:
                target_user = CustomUser.objects.get(id=user_id)
                if hasattr(target_user, 'tutor_profile'):
                    bookings = Booking.objects.filter(
                        tutor=target_user,  # Use the user, not the profile
                        date__range=[start_date, end_date]
                    )
                else:
                    bookings = Booking.objects.none()
            except CustomUser.DoesNotExist:
                bookings = Booking.objects.none()
        else:
            # Default behavior
            if hasattr(user, 'tutor_profile'):
                bookings = Booking.objects.filter(
                    tutor=user,  # Use the user, not the profile
                    date__range=[start_date, end_date]
                )
            else:
                bookings = Booking.objects.none()
        
        serializer = self.get_serializer(bookings, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def available_slots(self, request):
        """Get available time slots for a specific tutor and date"""
        tutor_id = request.query_params.get('tutor_id')
        date_str = request.query_params.get('date')
        
        if not tutor_id or not date_str:
            return Response(
                {'error': 'tutor_id and date parameters are required'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            date_obj = datetime.strptime(date_str, '%Y-%m-%d').date()
            tutor = CustomUser.objects.get(id=tutor_id)
        except (ValueError, CustomUser.DoesNotExist):
            return Response(
                {'error': 'Invalid tutor_id or date format'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Get existing bookings for this tutor on this date
        existing_bookings = Booking.objects.filter(
            tutor=tutor,
            date=date_obj,
            status__in=['pending', 'confirmed']
        ).values_list('start_time', flat=True)
        
        # Generate available time slots (you can customize this logic)
        # This example shows hourly slots from 8 AM to 6 PM
        available_slots = []
        start_hour = 8
        end_hour = 18
        
        for hour in range(start_hour, end_hour):
            slot_time = time(hour, 0)
            if slot_time not in existing_bookings:
                available_slots.append(slot_time.strftime('%H:%M'))
        
        return Response({'available_slots': available_slots})
    


class ReviewViewSet(viewsets.ModelViewSet):
    queryset = Review.objects.all()
    serializer_class = ReviewSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        queryset = super().get_queryset()
        tutor_id = self.request.query_params.get('tutor_id')
        
        if tutor_id:
            queryset = queryset.filter(tutor_id=tutor_id)
        
        return queryset

    def perform_create(self, serializer):
        """Create a review and update tutor rating"""
        review = serializer.save()
        
        # Update tutor's rating and review count
        tutor = review.tutor
        reviews = Review.objects.filter(tutor=tutor)
        tutor.total_reviews = reviews.count()
        tutor.rating = reviews.aggregate(avg_rating=Avg('rating'))['avg_rating'] or 0
        tutor.save()

class TutorDetailView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    
    def get(self, request, user_id):
        try:
            user = CustomUser.objects.get(id=user_id)
            if hasattr(user, 'tutor_profile'):
                serializer = TutorProfileSerializer(user.tutor_profile)
                return Response(serializer.data)
            else:
                return Response({'error': 'User is not a tutor'}, status=status.HTTP_404_NOT_FOUND)
        except CustomUser.DoesNotExist:
            return Response({'error': 'User not found'}, status=status.HTTP_404_NOT_FOUND)

class StudentUserDetailView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    
    def get(self, request, user_id):
        try:
            user = CustomUser.objects.get(id=user_id)
            if hasattr(user, 'student_profile'):
                serializer = StudentProfileSerializer(user.student_profile)
                return Response(serializer.data)
            else:
                return Response({'error': 'User is not a student'}, status=status.HTTP_404_NOT_FOUND)
        except CustomUser.DoesNotExist:
            return Response({'error': 'User not found'}, status=status.HTTP_404_NOT_FOUND)