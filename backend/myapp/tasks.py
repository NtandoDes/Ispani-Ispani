from celery import shared_task
from django.utils import timezone
from datetime import timedelta
from .models import Booking, TutorEarnings
from decimal import Decimal

@shared_task
def calculate_weekly_earnings():
    today = timezone.now().date()
    start_of_week = today - timedelta(days=today.weekday() + 7)
    end_of_week = start_of_week + timedelta(days=6)

    tutors = Booking.objects.filter(
        is_paid=True,
        is_processed=False,
        scheduled_time__date__range=[start_of_week, end_of_week]
    ).values_list('tutor', flat=True).distinct()

    for tutor_id in tutors:
        tutor_bookings = Booking.objects.filter(
            tutor_id=tutor_id,
            is_paid=True,
            is_processed=False,
            scheduled_time__date__range=[start_of_week, end_of_week]
        )
        total = sum([50.00 for _ in tutor_bookings])  # Example fixed R50/session
        commission = total * Decimal('0.10')
        net = total - commission

        TutorEarnings.objects.create(
            tutor_id=tutor_id,
            week_start=start_of_week,
            week_end=end_of_week,
            total_earnings=total,
            platform_commission=commission,
            net_earnings=net
        )

        tutor_bookings.update(is_processed=True)