from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import StudentProfile, Group

@receiver(post_save, sender=StudentProfile)
def assign_student_to_group(sender, instance, created, **kwargs):
    if created:  # Only when a new student profile is created
        # Find the group(s) that match the student's year_of_study and field_of_study
        
        matching_groups = Group.objects.filter(year_of_study=instance.year_of_study,course=instance.course)

        matching_groups = Group.objects.filter(hobbies=instance.hobbies )
        
        # Add the student to each matching group
        for group in matching_groups:
            group.members.add(instance)
