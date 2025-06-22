from django.core.management.base import BaseCommand
from django.db import transaction
from myapp.models.groups import GroupChat
from myapp.models import ChatRoom


class Command(BaseCommand):
    help = 'Sync GroupChat members to their corresponding ChatRoom members'

    def handle(self, *args, **options):
        self.stdout.write('Starting sync of ChatRoom members...')
        
        synced_count = 0
        created_count = 0
        
        with transaction.atomic():
            for group in GroupChat.objects.all():
                # Get or create corresponding ChatRoom
                chat_room, created = ChatRoom.objects.get_or_create(
                    id=group.id,
                    defaults={'name': group.name}
                )
                
                if created:
                    created_count += 1
                    self.stdout.write(f'Created ChatRoom for group: {group.name}')
                
                # Get current ChatRoom members
                current_members = set(chat_room.members.all())
                # Get GroupChat members
                group_members = set(group.members.all())
                
                # Add missing members to ChatRoom
                members_to_add = group_members - current_members
                if members_to_add:
                    chat_room.members.add(*members_to_add)
                    synced_count += len(members_to_add)
                    self.stdout.write(
                        f'Added {len(members_to_add)} members to ChatRoom for group: {group.name}'
                    )
                
                # Remove extra members from ChatRoom (optional)
                members_to_remove = current_members - group_members
                if members_to_remove:
                    chat_room.members.remove(*members_to_remove)
                    self.stdout.write(
                        f'Removed {len(members_to_remove)} members from ChatRoom for group: {group.name}'
                    )
        
        self.stdout.write(
            self.style.SUCCESS(
                f'Successfully synced {synced_count} members across all groups. '
                f'Created {created_count} new ChatRooms.'
            )
        )