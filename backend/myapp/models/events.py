from django.forms import ValidationError
from .import models

class Event(models.Model):
    EVENT_TYPE_CHOICES = [
        ('social', 'Social Gathering'),
        ('sports', 'Sports Activity'),
        ('game', 'Game Night'),
        ('study', 'Group Study'),
        ('outdoor', 'Outdoor Activity'),
        ('arts', 'Arts & Crafts'),
        ('other', 'Other')
    ]
    
    RECURRENCE_CHOICES = [
        ('one-time', 'One-time Event'),
        ('daily', 'Daily'),
        ('weekly', 'Weekly'),
        ('biweekly', 'Every Two Weeks'),
        ('monthly', 'Monthly')
    ]
    
    title = models.CharField(max_length=100)
    description = models.TextField()
    event_type = models.CharField(max_length=20, choices=EVENT_TYPE_CHOICES)
    creator = models.ForeignKey('CustomUser', on_delete=models.CASCADE, related_name='created_events')
    location = models.CharField(max_length=200)
    start_time = models.DateTimeField()
    end_time = models.DateTimeField()
    max_participants = models.PositiveIntegerField(default=10)
    is_public = models.BooleanField(default=True)
    recurrence = models.CharField(max_length=20, choices=RECURRENCE_CHOICES, default='one-time')
    recurrence_end_date = models.DateField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    invite_link = models.CharField(max_length=50, unique=True, null=True, blank=True)
    tags = models.ManyToManyField('EventTag', related_name='events', blank=True)
    
    def clean(self):
        if self.start_time >= self.end_time:
            raise ValidationError("End time must be after start time")
        if self.recurrence != 'one-time' and not self.recurrence_end_date:
            raise ValidationError("Recurring events must have an end date")
        
    def __str__(self):
        return f"{self.title} - {self.start_time.strftime('%d %b %Y, %H:%M')}"

class EventParticipant(models.Model):
    ROLE_CHOICES = [
        ('organizer', 'Organizer'),
        ('participant', 'Participant')
    ]
    
    STATUS_CHOICES = [
        ('invited', 'Invited'),
        ('going', 'Going'),
        ('maybe', 'Maybe'),
        ('declined', 'Declined')
    ]
    
    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name='participants')
    user = models.ForeignKey('CustomUser', on_delete=models.CASCADE, related_name='events')
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='participant')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='going')
    joined_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        unique_together = ('event', 'user')
        
    def __str__(self):
        return f"{self.user.username} - {self.event.title} ({self.get_status_display()})"

class EventTag(models.Model):
    name = models.CharField(max_length=50, unique=True)
    
    def __str__(self):
        return self.name

class EventComment(models.Model):
    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name='comments')
    user = models.ForeignKey('CustomUser', on_delete=models.CASCADE, related_name='event_comments')
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"Comment by {self.user.username} on {self.event.title}"

class EventMedia(models.Model):
    MEDIA_TYPE_CHOICES = [
        ('image', 'Image'),
        ('video', 'Video'),
        ('document', 'Document')
    ]
    
    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name='media')
    file = models.FileField(upload_to='event_media/')
    media_type = models.CharField(max_length=20, choices=MEDIA_TYPE_CHOICES)
    title = models.CharField(max_length=100, blank=True)
    uploaded_by = models.ForeignKey('CustomUser', on_delete=models.CASCADE)
    uploaded_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"{self.get_media_type_display()} for {self.event.title}"