from django.db import models
from django.utils.crypto import get_random_string
from .authentication import CustomUser


class GroupType(models.TextChoices):
    INSTITUTION = 'institution', 'Institution-based'
    CITY_HOBBY = 'city_hobby', 'City-Hobby-based'
    GENERAL = 'general', 'General'

class GroupChat(models.Model):
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True, null=True)
    group_type = models.CharField(
        max_length=20,
        choices=GroupType.choices,
        default=GroupType.GENERAL
    )
    city = models.CharField(max_length=100, blank=True, null=True)
    institution = models.CharField(max_length=200, blank=True, null=True)
    hobbies = models.ManyToManyField('Hobby', blank=True, related_name='groups')
    
    members = models.ManyToManyField(CustomUser, through='GroupMembership', related_name='groups_chats')
    admins = models.ManyToManyField(CustomUser, related_name='admin_groups', blank=True)
    is_dynamic = models.BooleanField(default=False, help_text="Whether this group was automatically created based on user profiles")
    image = models.ImageField(upload_to='group_images/', null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name
    
class GroupMembership(models.Model):
    ROLE_CHOICES = (
        ('admin', 'Admin'),
        ('member', 'Member'),
    )
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE)
    group = models.ForeignKey(GroupChat, on_delete=models.CASCADE)
    role = models.CharField(max_length=20, choices=ROLE_CHOICES)
    joined_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user', 'group')

class Hobby(models.Model):
    name = models.CharField(max_length=100, unique=True)

    def __str__(self):
        return self.name

class GroupMessage(models.Model):
    chat = models.ForeignKey(GroupChat, on_delete=models.CASCADE)
    sender = models.ForeignKey(CustomUser, on_delete=models.CASCADE)
    content = models.TextField()
    timestamp = models.DateTimeField(auto_now_add=True)
    is_pinned = models.BooleanField(default=False)