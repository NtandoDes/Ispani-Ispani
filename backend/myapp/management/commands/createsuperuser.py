from django.core.management import BaseCommand
from django.contrib.auth.management.commands import createsuperuser
from django.core.management import call_command

class Command(createsuperuser.Command):
    def handle(self, *args, **kwargs):
        # Create superuser
        super().handle(*args, **kwargs)
        
        # After superuser creation, manually update any necessary fields
        from myapp.models import Group

        # Update all groups to set a default 'field_of_study' value
        Group.objects.filter(field_of_study__isnull=True).update(field_of_study='Default Study Field')
        print("Field of Study for groups updated.")
