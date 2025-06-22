from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils import timezone
from django.core.validators import MinValueValidator, MaxValueValidator


class CustomUser(AbstractUser):
    
    roles = models.JSONField(default=list)
    email = models.EmailField(unique=True)
    hobbies= models.TextField()
    bio = models.TextField(blank=True, null=True)
    active_role = models.CharField(max_length=30, blank=True, null=True)
    city = models.CharField(max_length=100, null=True, blank=True)
    profile_picture = models.ImageField(upload_to='profile_pics/', blank=True, null=True)
    username = models.CharField(max_length=150, unique=True)

    def get_profile_picture_url(self):
        if self.profile_picture:
            return self.profile_picture.url  
        return None
    
    class Meta:
        verbose_name = 'User'
        verbose_name_plural = 'Users'
    
    def has_student_profile(self):
        return hasattr(self, 'student_profile')
    
    def has_tutor_profile(self):
        return hasattr(self, 'tutor_profile')
    
    def has_jobseeker_profile(self):
        return hasattr(self, 'jobseeker_profile')
    
    def has_hstudent_profile(self):
        return hasattr(self, 'hstudent_profile')
    
    def get_display_name(self):
        """Get the display name for the user based on their active role"""
        if self.active_role == 'student' and self.has_student_profile():
            return f"Student: {self.username}"
        elif self.active_role == 'tutor' and self.has_tutor_profile():
            return f"Tutor: {self.username}"
        elif self.active_role == 'hstudent' and self.has_hstudent_profile():
            return f"High School Student: {self.username}"
        return self.username
    
    def __str__(self):
        return self.username
    

class StudentProfile(models.Model):
    # Remove the separate ID - use the User's ID as the primary key
    user = models.OneToOneField(
        CustomUser, 
        on_delete=models.CASCADE, 
        related_name='student_profile',
        primary_key=True  # This makes the user_id the primary key
    )
    city = models.CharField(max_length=100, null=True, blank=True)
    year_of_study = models.IntegerField(null=True, blank=True)
    course = models.CharField(max_length=100, null=True, blank=True)
    hobbies = models.TextField(null=True, blank=True)
    qualification = models.TextField(null=True, blank=True)
    bio = models.TextField(blank=True, null=True)
    profile_picture = models.ImageField(upload_to='profile_pics/', blank=True, null=True)
    institution = models.CharField(max_length=50, null=True, blank=True)
    
    def __str__(self):
        return f"Student Profile: {self.user.username}"

class HStudents(models.Model):
    # Remove the separate ID - use the User's ID as the primary key
    user = models.OneToOneField(
        CustomUser, 
        on_delete=models.CASCADE, 
        related_name='hstudent_profile',
        primary_key=True  # This makes the user_id the primary key
    )
    city = models.CharField(max_length=100, null=True, blank=True)
    hobbies = models.TextField(null=True, blank=True)
    schoolName = models.CharField(max_length=100, null=True, blank=True)
    studyLevel = models.CharField(max_length=100, null=True, blank=True)
    subjects = models.TextField(null=True, blank=True)
    bio = models.TextField(blank=True, null=True)
    profile_picture = models.ImageField(upload_to='profile_pics/', blank=True, null=True)
    
    def __str__(self):
        return f"High School Student Profile: {self.user.username}"

class TutorProfile(models.Model):
    # Remove the separate ID - use the User's ID as the primary key
    user = models.OneToOneField(
        CustomUser, 
        on_delete=models.CASCADE, 
        related_name='tutor_profile',
        primary_key=True  # This makes the user_id the primary key
    )
    place = models.CharField(max_length=100, null=True, blank=True)
    city = models.CharField(max_length=100, null=True, blank=True)
    phone_number = models.IntegerField()
    hourly_rate = models.DecimalField(max_digits=10, decimal_places=2)
    address = models.TextField(blank=True)
    is_available_online = models.BooleanField(default=True)
    is_available_physical = models.BooleanField(default=True)
    rating = models.DecimalField(
        max_digits=3,
        decimal_places=2,
        default=0.00,
        validators=[MinValueValidator(0.00), MaxValueValidator(5.00)]
    )
    total_reviews = models.IntegerField(default=0)
    cv = models.FileField(upload_to='profile_pics/', blank=True, null=True)
    bio = models.TextField(blank=True, null=True)
    profile_picture = models.ImageField(upload_to='profile_pics/', blank=True, null=True)
    
    # Fixed: Use string reference to Subject model
    subjects = models.ManyToManyField('Subject', blank=True, related_name='tutors')
    
    def __str__(self):
        return f"Tutor Profile: {self.user.username}"
    
class ServiceProvider(models.Model):
     user = models.OneToOneField(CustomUser, on_delete=models.CASCADE, related_name='serviceprovider_profile', primary_key=True)
     city = models.CharField(max_length=100, null=True, blank=True)
     company = models.CharField(max_length=100)  
     about = models.CharField(max_length=100)  
     usageType = models.TextField()
     sectors = models.TextField()
     hobbies= models.TextField()
     bio = models.TextField(blank=True, null=True)
     profile_picture = models.ImageField(upload_to='profile_pics/', blank=True, null=True)
     serviceNeeds=models.TextField()

     def __str__(self):
        return f"ServiceProvider Profile: {self.user.username}"
     
class JobSeeker(models.Model):

    user = models.OneToOneField(CustomUser, on_delete=models.CASCADE, related_name='jobseeker_profile', primary_key=True)
    city = models.CharField(max_length=100, null=True, blank=True)
    cellnumber = models.IntegerField(null=True, blank=True)
    status = models.TextField(null=True, blank=True)
    usage = models.TextField(null=True, blank=True)
    hobbies= models.TextField()
    bio = models.TextField(blank=True, null=True)
    profile_picture = models.ImageField(upload_to='profile_pics/', blank=True, null=True)


    def __str__(self):
        return f"JobSeeker Profile: {self.user.username}"
    
class Subject(models.Model):
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name
    
class ConnectionRequest(models.Model):
    from_user = models.ForeignKey(CustomUser, related_name='sent_requests', on_delete=models.CASCADE)
    to_user = models.ForeignKey(CustomUser, related_name='received_requests', on_delete=models.CASCADE)
    status = models.CharField(max_length=20, choices=[
        ('pending', 'Pending'),
        ('accepted', 'Accepted'),
        ('rejected', 'Rejected'),
    ], default='pending')
    created_at = models.DateTimeField(default=timezone.now)
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('from_user', 'to_user')

    def __str__(self):
        return f"{self.from_user} → {self.to_user} ({self.status})"