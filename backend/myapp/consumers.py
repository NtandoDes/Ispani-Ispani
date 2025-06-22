# myapp/consumers.py
import json
import logging
from urllib.parse import parse_qs
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.contrib.auth import get_user_model
from rest_framework_simplejwt.tokens import AccessToken
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError
from django.db.models import Q

from .models.authentication import ConnectionRequest
from .models import ChatRoom, ChatMessage,PrivateChat, PrivateMessage

User = get_user_model()
logger = logging.getLogger(__name__)

class ChatConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        try:
            # Get room ID from URL
            self.room_id = self.scope['url_route']['kwargs']['room_id']
            self.room_group_name = f'chat_{self.room_id}'
            
            # Get token from query string or headers
            token = await self.get_token()
            
            if not token:
                logger.error("No token provided")
                await self.close(code=4001)
                return
                
            # Authenticate user with JWT token
            try:
                access_token = AccessToken(token)
                user_id = access_token['user_id']
                self.user = await database_sync_to_async(User.objects.get)(id=user_id)
                logger.info(f"User {self.user.username} authenticated successfully")
            except (InvalidToken, TokenError) as e:
                logger.error(f"Invalid token: {e}")
                await self.close(code=4002)
                return
            except User.DoesNotExist:
                logger.error(f"User with id {user_id} does not exist")
                await self.close(code=4003)
                return
            
            # Verify user has access to this room
            try:
                self.room = await database_sync_to_async(ChatRoom.objects.get)(id=self.room_id)
                
                # Check if user is a member of the room
                is_member = await database_sync_to_async(
                    lambda: self.room.members.filter(id=self.user.id).exists()
                )()
                
                if not is_member:
                    logger.error(f"User {self.user.username} is not a member of room {self.room_id}")
                    await self.close(code=4004)
                    return
                    
            except ChatRoom.DoesNotExist:
                logger.error(f"Room {self.room_id} does not exist")
                await self.close(code=4005)
                return
            
            # Join room group
            await self.channel_layer.group_add(
                self.room_group_name,
                self.channel_name
            )
            
            # Accept the connection
            await self.accept()
            logger.info(f"User {self.user.username} connected to room {self.room_id}")
            
            # Send connection confirmation
            await self.send(text_data=json.dumps({
                'type': 'connection_established',
                'room_id': self.room_id,
                'user': {
                    'id': self.user.id,
                    'username': self.user.username
                }
            }))
            
        except Exception as e:
            logger.error(f"Error in connect: {e}")
            await self.close(code=4000)

    async def get_token(self):
        """Extract token from query string or headers"""
        # Try query string first
        query_string = self.scope.get('query_string', b'').decode('utf-8')
        if query_string:
            try:
                params = dict(param.split('=', 1) for param in query_string.split('&') if '=' in param)
                token = params.get('token')
                if token:
                    return token
            except Exception as e:
                logger.error(f"Error parsing query string: {e}")
        
        # Try headers
        headers = dict(self.scope.get('headers', []))
        auth_header = headers.get(b'authorization', b'').decode('utf-8')
        if auth_header.startswith('Bearer '):
            return auth_header[7:]  # Remove 'Bearer ' prefix
            
        return None

    async def disconnect(self, close_code):
        """Called when the WebSocket closes for any reason."""
        try:
            # Leave room group
            if hasattr(self, 'room_group_name'):
                await self.channel_layer.group_discard(
                    self.room_group_name,
                    self.channel_name
                )
            
            if hasattr(self, 'user') and hasattr(self, 'room_id'):
                logger.info(f"User {self.user.username} disconnected from room {self.room_id} with code: {close_code}")
            else:
                logger.info(f"Client disconnected with code: {close_code}")
                
        except Exception as e:
            logger.error(f"Error in disconnect: {e}")

    async def receive(self, text_data):
        """Handle incoming WebSocket messages"""
        try:
            data = json.loads(text_data)
            logger.info(f"Received message: {data}")

            # Ensure data is a dict
            if not isinstance(data, dict):
                raise ValueError("Expected JSON object")

            message_type = data.get('type', 'message')

            if message_type == 'ping':
                await self.send(text_data=json.dumps({'type': 'pong'}))
            elif message_type == 'message':
                await self.handle_chat_message(data)
            else:
                logger.warning(f"Unknown message type: {message_type}")

        except (json.JSONDecodeError, ValueError) as e:
            logger.error(f"Invalid message format: {e}")
            await self.send_error("Invalid message format. Please send JSON with type and content.")
        except Exception as e:
            logger.error(f"Error in receive: {e}")
            await self.send_error("An error occurred while processing your message.")

    async def handle_chat_message(self, data):
        """Handle incoming chat message"""
        # Handle both 'content' and 'text' fields for backward compatibility
        message_text = data.get('content', data.get('text', '')).strip()
        
        if not message_text:
            await self.send_error("Message content cannot be empty")
            return
        
        try:
            # Create message in database
            message = await database_sync_to_async(ChatMessage.objects.create)(
                room_id=self.room_id,
                sender=self.user,
                text=message_text  
            )
            
            logger.info(f"Message created in database: {message.id}")
            
            # Prepare message data to send to group
            message_data = {
                'type': 'message',  # Changed from 'chat_message' to match Flutter expectation
                'id': message.id,
                'text': message.text,  
                'sender': {
                    'id': self.user.id,
                    'username': self.user.username,
                },
                'created_at': message.created_at.isoformat(), 
                'room_id': self.room_id
            }
            
            # Send message to room group
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    'type': 'chat_message',  # This is the method name to call
                    'message': message_data
                }
            )
            
            logger.info(f"Message sent to group: {self.room_group_name}")
            
        except Exception as e:
            logger.error(f"Error creating message: {e}")
            await self.send_error("Failed to send message")

    async def send_error(self, error_message):
        """Send error message to client"""
        await self.send(text_data=json.dumps({
            'type': 'error',
            'message': error_message
        }))

    async def chat_message(self, event):
        """Called when a message is sent to the group"""
        try:
            message = event['message']
            logger.info(f"Sending message to client: {message}")
            await self.send(text_data=json.dumps(message))
        except Exception as e:
            logger.error(f"Error sending message to client: {e}")
class PrivateChatConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        try:
            
            self.other_user_id = int(self.scope['url_route']['kwargs']['user_id'])  
            
            # Get token from query parameters
            token = self.get_token_from_scope()
            if not token:
                logger.warning(f"No token provided for chat with user {self.other_user_id}")
                await self.close(code=4001)
                return

            # Authenticate user
            try:
                access_token = AccessToken(token)
                user_id = access_token['user_id']
                self.user = await self.get_user_by_id(user_id)
                if not self.user:
                    logger.warning(f"User {user_id} not found")
                    await self.close(code=4001)
                    return
            except (InvalidToken, TokenError) as e:
                logger.warning(f"Invalid token for chat with user {self.other_user_id}: {e}")
                await self.close(code=4001)
                return

            # Get the other user
            self.other_user = await self.get_user_by_id(self.other_user_id)
            if not self.other_user:
                logger.warning(f"Other user {self.other_user_id} not found")
                await self.close(code=4004)
                return

            # Check if users are connected - FIXED: using correct field names
            are_connected = await self.check_connection_status(self.user, self.other_user)
            if not are_connected:
                logger.warning(f"Users {self.user.id} and {self.other_user_id} are not connected")
                await self.close(code=4004)
                return

            # Create a consistent room name based on user IDs (smaller ID first)
            user_ids = sorted([self.user.id, self.other_user_id])
            self.room_group_name = f'private_chat_{user_ids[0]}_{user_ids[1]}'

            # Add to group and accept connection
            await self.channel_layer.group_add(
                self.room_group_name,
                self.channel_name
            )

            await self.accept()
            
            # Send connection confirmation
            await self.send(text_data=json.dumps({
                'type': 'connection_established',
                'other_user': {
                    'id': self.other_user.id,
                    'username': self.other_user.username
                },
                'current_user': {
                    'id': self.user.id,
                    'username': self.user.username
                }
            }))
            
            logger.info(f"User {self.user.username} connected to chat with {self.other_user.username}")

        except ValueError as e:
            logger.error(f"Invalid user_id in URL: {e}")
            await self.close(code=4000)
        except Exception as e:
            logger.error(f"Error in WebSocket connect: {e}")
            await self.close(code=4000)

    def get_token_from_scope(self):
        """Extract JWT token from WebSocket scope (query parameters)"""
        try:
            query_string = self.scope.get('query_string', b'').decode('utf-8')
            query_params = parse_qs(query_string)
            
            if 'token' in query_params:
                return query_params['token'][0]
                
            return None
        except Exception as e:
            logger.error(f"Error extracting token: {e}")
            return None

    @database_sync_to_async
    def get_user_by_id(self, user_id):
        """Get user by ID"""
        try:
            return User.objects.get(id=user_id)
        except User.DoesNotExist:
            return None

    @database_sync_to_async
    def get_or_create_chat(self, user1, user2):
        """Get existing chat or create new one"""
        try:
            # Try to find existing chat (either direction)
            chat = PrivateChat.objects.filter(
                Q(user1=user1, user2=user2) | Q(user1=user2, user2=user1)
            ).first()
            
            if not chat:
                # Create new chat with consistent ordering (smaller ID as user1)
                if user1.id < user2.id:
                    chat = PrivateChat.objects.create(user1=user1, user2=user2)
                else:
                    chat = PrivateChat.objects.create(user1=user2, user2=user1)
                    
            return chat
        except Exception as e:
            logger.error(f"Error getting or creating chat: {e}")
            return None

    @database_sync_to_async
    def check_connection_status(self, user1, user2):
        """Check if users are still connected - FIXED: using correct field names"""
        return ConnectionRequest.objects.filter(
            Q(from_user=user1, to_user=user2) | Q(from_user=user2, to_user=user1),
            status='accepted'
        ).exists()

    @database_sync_to_async
    def create_message(self, chat, sender, content):
        """Create a new message"""
        return PrivateMessage.objects.create(
            chat=chat,
            sender=sender,
            content=content 
        )

    async def disconnect(self, close_code):
        try:
            # Check if room_group_name exists before trying to use it
            if hasattr(self, 'room_group_name'):
                await self.channel_layer.group_discard(
                    self.room_group_name,
                    self.channel_name
                )
            if hasattr(self, 'user') and hasattr(self, 'other_user'):
                logger.info(f"User {self.user.username} disconnected from chat with {self.other_user.username} with code: {close_code}")
        except Exception as e:
            logger.error(f"Error in disconnect: {e}")

    async def receive(self, text_data):
        try:
            data = json.loads(text_data)
            message_type = data.get('type', 'message')

            if message_type == 'message':
                await self.handle_message(data)
            elif message_type == 'typing':
                await self.handle_typing(data)
            elif message_type == 'file':
                await self.handle_file(data)
            else:
                logger.warning(f"Unknown message type: {message_type}")

        except json.JSONDecodeError:
            await self.send(text_data=json.dumps({
                'type': 'error', 
                'message': 'Invalid JSON format'
            }))
        except Exception as e:
            logger.error(f"Error in receive: {e}")
            await self.send(text_data=json.dumps({
                'type': 'error', 
                'message': 'Internal server error'
            }))

    async def handle_message(self, data):
        """Handle regular text messages"""
        message_text = data.get('content', '').strip()

        if not message_text:
            await self.send(text_data=json.dumps({
                'type': 'error', 
                'message': 'Message cannot be empty'
            }))
            return

        # Check if users are still connected - FIXED: using correct field names
        are_connected = await self.check_connection_status(self.user, self.other_user)
        if not are_connected:
            await self.send(text_data=json.dumps({
                'type': 'error', 
                'message': 'Cannot send message - users are not connected'
            }))
            return

        # Get or create chat automatically
        chat = await self.get_or_create_chat(self.user, self.other_user)
        if not chat:
            await self.send(text_data=json.dumps({
                'type': 'error', 
                'message': 'Failed to create chat'
            }))
            return

        # Create message in database
        message = await self.create_message(chat, self.user, message_text)

        # Prepare message data
        message_data = {
            'type': 'message',
            'id': message.id,
            'content': message.content,
            'sender': {
                'id': self.user.id, 
                'username': self.user.username
            },
            'created_at': message.created_at.isoformat(),
            'chat_id': chat.id
        }

        # Broadcast to group
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'private_chat_message',
                'message': message_data
            }
        )

    async def handle_typing(self, data):
        """Handle typing notifications"""
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'typing_notification',
                'message': {
                    'type': 'typing',
                    'sender': {
                        'id': self.user.id,
                        'username': self.user.username
                    },
                    'other_user_id': self.other_user_id
                }
            }
        )

    async def handle_file(self, data):
        """Handle file uploads"""
        file_data = data.get('file', '')
        filename = data.get('filename', 'Unknown file')
        filesize = data.get('filesize', 0)

        if not file_data or not filename:
            await self.send(text_data=json.dumps({
                'type': 'error', 
                'message': 'Invalid file data'
            }))
            return

        # Get or create chat automatically
        chat = await self.get_or_create_chat(self.user, self.other_user)
        if not chat:
            await self.send(text_data=json.dumps({
                'type': 'error', 
                'message': 'Failed to create chat'
            }))
            return

        # Create message with file info
        message_text = f"📎 {filename}"
        message = await self.create_message(chat, self.user, message_text)

        # Prepare message data
        message_data = {
            'type': 'message',
            'id': message.id,
            'content': message.content,
            'file': file_data,
            'filename': filename,
            'filesize': filesize,
            'sender': {
                'id': self.user.id, 
                'username': self.user.username
            },
            'created_at': message.created_at.isoformat(),
            'chat_id': chat.id
        }

        # Broadcast to group
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'private_chat_message',
                'message': message_data
            }
        )

    async def private_chat_message(self, event):
        """Send message to WebSocket"""
        await self.send(text_data=json.dumps(event['message']))

    async def typing_notification(self, event):
        """Send typing notification to WebSocket"""
        await self.send(text_data=json.dumps(event['message']))
        
# Custom WebSocket middleware for better error handling
class TokenAuthMiddleware:
    """Custom middleware for token authentication"""
    
    def __init__(self, inner):
        self.inner = inner
    
    async def __call__(self, scope, receive, send):
        return await self.inner(scope, receive, send)