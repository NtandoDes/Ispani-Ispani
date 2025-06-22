from django.db import models
from django.contrib.auth.models import AbstractUser
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils import timezone
from datetime import time
from decimal import Decimal
import uuid
from .authentication import CustomUser, StudentProfile, Subject, TutorProfile
 
class Booking(models.Model):
    BOOKING_STATUS = (
        ('pending', 'Pending'),
        ('confirmed', 'Confirmed'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
    )
    
    BOOKING_TYPE = (
        ('online', 'Online'),
        ('physical', 'Physical'),
    )
    
    MEETING_PLATFORMS = (
        ('Zoom', 'Zoom'),
        ('Microsoft Teams', 'Microsoft Teams'),
        ('Google Meet', 'Google Meet'),
    )

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    student = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='student_bookings')
    tutor = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='tutor_bookings')
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE)
    
    booking_type = models.CharField(max_length=10, choices=BOOKING_TYPE, default='online')
    platform = models.CharField(  # Changed from 'meeting_platform' to 'platform'
        max_length=20, 
        choices=MEETING_PLATFORMS, 
        blank=True, 
        null=True
    )
    meeting_link = models.URLField(blank=True, null=True)
    location = models.TextField(blank=True, null=True)  # For physical meetings
    
    date = models.DateField()
    start_time = models.TimeField(default=time(9, 0))  # Default 9:00 AM
    end_time = models.TimeField(default=time(10, 0))   # Default 10:00 AM
    duration = models.IntegerField(help_text="Duration in minutes", default=60)
    
    notes = models.TextField(blank=True)
    special_requirements = models.TextField(blank=True)
    
    status = models.CharField(max_length=10, choices=BOOKING_STATUS, default='pending')
    
    # Pricing
    hourly_rate = models.DecimalField(max_digits=10, decimal_places=2)
    total_cost = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        default=Decimal('25.00')
    )
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    confirmed_at = models.DateTimeField(blank=True, null=True)
    completed_at = models.DateTimeField(blank=True, null=True)

        # Add to your Booking model
    rescheduled_at = models.DateTimeField(null=True, blank=True)
    reschedule_reason = models.TextField(blank=True)


    class Meta:
        ordering = ['-created_at']
        unique_together = ['tutor', 'date', 'start_time']

    def save(self, *args, **kwargs):
        # Calculate total cost based on duration and hourly rate
        if self.duration and self.hourly_rate:
            hours = Decimal(str(self.duration)) / Decimal('60')
            self.total_cost = Decimal(str(self.hourly_rate)) * hours
        
        # Set confirmed_at when status changes to confirmed
        if self.status == 'confirmed' and not self.confirmed_at:
            self.confirmed_at = timezone.now()
        
        # Set completed_at when status changes to completed
        if self.status == 'completed' and not self.completed_at:
            self.completed_at = timezone.now()
            
        super().save(*args, **kwargs)
        
    def __str__(self):
        return f"{self.student.username} -> {self.tutor.username} - {self.date} {self.start_time}"

class TutorAvailability(models.Model):
    DAYS_OF_WEEK = (
        ('monday', 'Monday'),
        ('tuesday', 'Tuesday'),
        ('wednesday', 'Wednesday'),
        ('thursday', 'Thursday'),
        ('friday', 'Friday'),
        ('saturday', 'Saturday'),
        ('sunday', 'Sunday'),
    )

    tutor = models.ForeignKey(TutorProfile, on_delete=models.CASCADE, related_name='availability')
    day_of_week = models.CharField(max_length=10, choices=DAYS_OF_WEEK)
    start_time = models.TimeField()
    end_time = models.TimeField()
    is_available = models.BooleanField(default=True)

    class Meta:
        unique_together = ['tutor', 'day_of_week', 'start_time']

    def __str__(self):
        return f"{self.tutor} - {self.get_day_of_week_display()} {self.start_time}-{self.end_time}"

class Review(models.Model):
    booking = models.OneToOneField(Booking, on_delete=models.CASCADE, related_name='review')
    student = models.ForeignKey(StudentProfile, on_delete=models.CASCADE, related_name='reviews_given')
    tutor = models.ForeignKey(TutorProfile, on_delete=models.CASCADE, related_name='reviews_received')
    rating = models.IntegerField(validators=[MinValueValidator(1), MaxValueValidator(5)])
    comment = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        # Update tutor's average rating
        self.update_tutor_rating()

    def update_tutor_rating(self):
        reviews = Review.objects.filter(tutor=self.tutor)
        if reviews.exists():
            avg_rating = reviews.aggregate(models.Avg('rating'))['rating__avg']
            self.tutor.rating = round(avg_rating, 2)
            self.tutor.total_reviews = reviews.count()
            self.tutor.save()

    def __str__(self):
        return f"Review for {self.tutor} by {self.student} - {self.rating} stars"