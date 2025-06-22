from django.core.mail import send_mail
from django.conf import settings
import jwt
import datetime
from django.contrib.auth.models import Group


def create_temp_jwt(payload, expires_in=300):  # 5 minutes default
    payload['exp'] = datetime.datetime.utcnow() + datetime.timedelta(seconds=expires_in)
    token = jwt.encode(payload, settings.SECRET_KEY, algorithm='HS256')
    return token

def decode_temp_jwt(token):
    try:
        return jwt.decode(token, settings.SECRET_KEY, algorithms=['HS256'])
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
        return None
    
    
def send_otp_email(email, otp):
    """
    Send OTP verification code to user's email
    """
    subject = "Your OTP Code"
    message = f"Your OTP code is {otp}. It expires in 5 minutes."
    from_email = settings.DEFAULT_FROM_EMAIL
    recipient_list = [email]
    
    return send_mail(
        subject,
        message,
        from_email,
        recipient_list,
        fail_silently=False,
    )

def send_booking_confirmation(booking):
    """
    Send booking confirmation email to student and tutor
    """
    # Student email
    student_subject = f"Booking Confirmation: {booking.subject}"
    student_message = f"""
    Hi {booking.student.username},
    
    Your booking with {booking.tutor.username} has been confirmed.
    
    Details:
    Subject: {booking.subject}
    Date: {booking.start_time.strftime('%A, %B %d, %Y')}
    Time: {booking.start_time.strftime('%I:%M %p')} - {booking.end_time.strftime('%I:%M %p')}
    
    Meeting link: {booking.meeting_link}
    
    Thank you for using our platform!
    """
    
    send_mail(
        student_subject,
        student_message,
        settings.DEFAULT_FROM_EMAIL,
        [booking.student.email],
        fail_silently=False,
    )
    
    # Tutor email
    tutor_subject = f"New Booking: {booking.subject}"
    tutor_message = f"""
    Hi {booking.tutor.username},
    
    You have a new confirmed booking.
    
    Details:
    Student: {booking.student.username}
    Subject: {booking.subject}
    Date: {booking.start_time.strftime('%A, %B %d, %Y')}
    Time: {booking.start_time.strftime('%I:%M %p')} - {booking.end_time.strftime('%I:%M %p')}
    
    Meeting link: {booking.meeting_link}
    
    Thank you for using our platform!
    """
    
    send_mail(
        tutor_subject,
        tutor_message,
        settings.DEFAULT_FROM_EMAIL,
        [booking.tutor.email],
        fail_silently=False,
    )

def assign_user_to_dynamic_group(user, role, city, institution=None, qualification=None):
    if role == "student" and institution and city:
        group_name = f"Students in {city} at {institution}"
    elif role == "tutor" and city :
        group_name = f"Tutors in {city}"
    elif role == "service provider" and city:
        group_name = f"Jobseekers in {city}"
    elif role == "hs student" and city:
        group_name = f"High School Students in {city}"
    else:
        group_name = f"{role.title()}s in {city}" 

    group, _ = Group.objects.get_or_create(name=group_name)
    user.groups.add(group)  