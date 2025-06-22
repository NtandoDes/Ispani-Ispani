
from django.db import models
from django.conf import settings
from .authentication import CustomUser

class ChatRoom(models.Model):
    name = models.CharField(max_length=255)
    chat_type = models.CharField(max_length=20, default='group')
    members = models.ManyToManyField(CustomUser, related_name='chat_rooms')
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name

class ChatMessage(models.Model):
    room = models.ForeignKey(ChatRoom, on_delete=models.CASCADE, related_name='messages')
    sender = models.ForeignKey(CustomUser, on_delete=models.CASCADE)
    text = models.TextField()  # Keep as 'text' to match database
    created_at = models.DateTimeField(auto_now_add=True)  # Keep as 'created_at'

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.sender.username}: {self.text[:50]}'

class MessageAttachment(models.Model):
    message = models.ForeignKey(ChatMessage, on_delete=models.CASCADE, related_name='attachments')
    file = models.FileField(upload_to='message_attachments/')
    attachment_type = models.CharField(max_length=50)
    thumbnail = models.ImageField(upload_to='message_thumbnails/', null=True, blank=True)

class PrivateChat(models.Model):
    user1 = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='private_chats_1')
    user2 = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='private_chats_2')
    created_at = models.DateTimeField(auto_now_add=True)

class PrivateMessage(models.Model):
    chat = models.ForeignKey(PrivateChat, on_delete=models.CASCADE, related_name='messages')
    sender = models.ForeignKey(CustomUser, on_delete=models.CASCADE)
    content = models.TextField()
    is_read = models.BooleanField(default=False)
    created_at= models.DateTimeField(auto_now_add=True)