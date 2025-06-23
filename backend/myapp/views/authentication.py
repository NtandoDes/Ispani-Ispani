import json
from django.shortcuts import get_object_or_404
from django.utils import timezone
from datetime import timedelta
from django.core.cache import cache
import uuid

from django.db.models import Q


from django.contrib.auth import authenticate, login, logout
from django.core.mail import send_mail
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_decode
from django.utils.http import urlsafe_base64_encode
from django.utils.encoding import force_str
from django.conf import settings
from django.contrib.auth.models import Group
from django.contrib.auth.tokens import default_token_generator

from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.views import APIView
from rest_framework.generics import ListAPIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework import status
from rest_framework import serializers
from rest_framework_simplejwt.tokens import RefreshToken

from ..models.messaging import ChatRoom
from ..models.authentication import  ConnectionRequest
from myapp.utils import  create_temp_jwt
from .groups import assign_user_to_dynamic_group
from ..models import CustomUser, StudentProfile, TutorProfile, HStudents, ServiceProvider,JobSeeker,GroupChat
from ..serializers.authentication import ConnectionRequestSerializer, PublicUserSerializer, StudentProfileSerializer, TutorProfileSerializer, UserSerializer, UserRegistrationSerializer
import logging
from django.db.models import Q
logger = logging.getLogger(__name__)

class UserDetailView(APIView):
    permission_classes = [IsAuthenticated]
    
    def get(self, request, user_id):
        try:
            user = CustomUser.objects.get(id=user_id)
            serializer = UserSerializer(user, context={'request': request})
            return Response(serializer.data, status=status.HTTP_200_OK)
        except CustomUser.DoesNotExist:
            return Response(
                {"error": "User not found"}, 
                status=status.HTTP_404_NOT_FOUND
            )
    
    def put(self, request, user_id):
        try:
            user = CustomUser.objects.get(id=user_id)
            
            # Check if the user is updating their own profile or has permission
            if user != request.user:
                return Response(
                    {"error": "Permission denied"}, 
                    status=status.HTTP_403_FORBIDDEN
                )
            
            # Handle roles field if it's a JSON string
            data = request.data.copy()
            if 'roles' in data and isinstance(data['roles'], str):
                try:
                    data['roles'] = json.loads(data['roles'])
                except json.JSONDecodeError:
                    data['roles'] = []
            
            serializer = UserSerializer(user, data=data, partial=True, context={'request': request})
            if serializer.is_valid():
                serializer.save()
                return Response(serializer.data, status=status.HTTP_200_OK)
            else:
                return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
                
        except CustomUser.DoesNotExist:
            return Response(
                {"error": "User not found"}, 
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            return Response(
                {"error": str(e)}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

class CurrentUserDetailView(APIView):
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        try:
            serializer = UserSerializer(request.user, context={'request': request})
            return Response(serializer.data, status=status.HTTP_200_OK)
        except Exception as e:
            return Response(
                {"error": str(e)}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    def put(self, request):
        try:
            # Handle roles field if it's a JSON string
            data = request.data.copy()
            if 'roles' in data and isinstance(data['roles'], str):
                try:
                    data['roles'] = json.loads(data['roles'])
                except json.JSONDecodeError:
                    data['roles'] = []
            
            serializer = UserSerializer(request.user, data=data, partial=True, context={'request': request})
            if serializer.is_valid():
                serializer.save()
                return Response(serializer.data, status=status.HTTP_200_OK)
            else:
                return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
                
        except Exception as e:
            return Response(
                {"error": str(e)}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

class UserSerializer(serializers.ModelSerializer):
    mutual_connections = serializers.SerializerMethodField()
    
    class Meta:
        model = CustomUser
        fields = (
            'id', 'username', 'email', 'password', 'first_name', 'last_name',
            'roles', 'active_role', 'city', 'profile_picture', 'bio', 
            'hobbies', 'mutual_connections'
        )
        extra_kwargs = {
            'password': {'write_only': True},
            'roles': {'required': False},
            'active_role': {'required': False},
            'city': {'required': False},
            'bio': {'required': False},
            'hobbies': {'required': False},
            'first_name': {'required': False},
            'last_name': {'required': False},
        }

    def get_mutual_connections(self, obj):
        # Return 0 if no context or request user available
        request = self.context.get('request')
        if not request or not request.user.is_authenticated:
            return 0
            
        # Calculate mutual connections logic here
        # For now, return 0 - you can implement the logic later
        return 0
        
    def create(self, validated_data):
        # Create a new user with a hashed password
        password = validated_data.pop('password', None)
        user = CustomUser.objects.create(**validated_data)
        if password:
            user.set_password(password)
            user.save()
        return user
    
    def update(self, instance, validated_data):
        # Handle password separately if provided
        password = validated_data.pop('password', None)
        
        # Update all other fields
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        
        # Hash and set password if provided
        if password:
            instance.set_password(password)
        
        instance.save()
        return instance

class StudentUserDetailView(APIView):
    permission_classes = [IsAuthenticated]
    
    student_profile = None
    student_id = None
    
    def get(self, request, user_id):
        try:
            user = CustomUser.objects.get(id=user_id)
            
            # Get student profile if exists
            student_profile = None
            if hasattr(user, 'student_profile'):
                student_profile = user.student_profile
                student_id = student_profile.id
            elif hasattr(user, 'student_profile'):
                    student_profile = user.student_profile
                    student_id = student_profile.id
            else:
            # If no separate student profile, use user's pk
                    student_id = user.pk

            # Prepare response data
            return Response({
                'pk': user.pk,
                'username': user.username,
                'email': user.email,
                'first_name': user.first_name,
                'last_name': user.last_name,
                'student_id': student_id,  # Add this field
                'student_profile': student_profile.id if student_profile else None
            })            
            return Response(response_data, status=status.HTTP_200_OK)
        
        except CustomUser.DoesNotExist:
            return Response(
                {"error": "User not found"}, 
                status=status.HTTP_404_NOT_FOUND
            )
        
class TutorViewSet(APIView):
    permission_classes = [IsAuthenticated]
    
    def get(self, request, user_id):
        try:
            user = CustomUser.objects.get(id=user_id)
            
            # Get student profile if exists
            tutor_profile = None
            if hasattr(user, 'tutor_profile'):
                tutor_profile = user.tutor_profile
            
            # Prepare response data
            response_data = {
                'user': UserSerializer(user).data,
                'tutor_profile': TutorProfileSerializer(tutor_profile).data if tutor_profile else None
            }
            
            return Response(response_data, status=status.HTTP_200_OK)
        except CustomUser.DoesNotExist:
            return Response(
                {"error": "User not found"}, 
                status=status.HTTP_404_NOT_FOUND
            )

class SignUpView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        email = request.data.get("email")
        password = request.data.get("password")
        username = request.data.get("username")

        if not email or not password or not username:
            return Response({"error": "Email, password and username are required"}, 
                          status=status.HTTP_400_BAD_REQUEST)

        if CustomUser.objects.filter(email=email).exists():
            return Response({"error": "Email already in use"}, 
                          status=status.HTTP_400_BAD_REQUEST)

        # Generate a 6-digit OTP
        otp = str(uuid.uuid4().int)[:6]

        # Display OTP in terminal for development purposes
        print(f"\n\n{'='*50}")
        print(f"OTP for {email}: {otp}")
        print(f"{'='*50}\n\n")
        
        # Store user registration data and OTP in cache
        cache.set(f"otp_{email}", {
            "otp": otp, 
            "password": password, 
            "username": username
        }, timeout=3600)  # OTP valid for 1 hour

        # Send the OTP via email with improved template
        subject = "Your Verification Code"
        message = f"""
        Hello {username},
        
        Thank you for registering with us. Please use the following verification code 
        to complete your registration:
        
        Verification Code: {otp}
        
        This code will expire in 1 hour. If you didn't request this, please ignore this email.
        
        Best regards,
        Your Ispani Team
        """

        try:
            send_mail(
                subject=subject,
                message=message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[email],
                fail_silently=False,
            )
            return Response({"message": "Verification code sent to your email"}, 
                          status=status.HTTP_200_OK)
        except Exception as e:
            return Response({"error": f"Failed to send email: {str(e)}"}, 
                          status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class VerifyOTPView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        email = request.data.get("email")
        otp = request.data.get("otp")
        
        if not email or not otp:
            return Response({"error": "Email and OTP are required"}, 
                          status=status.HTTP_400_BAD_REQUEST)
        
        # Retrieve stored data from cache
        cached_data = cache.get(f"otp_{email}")
        
        if not cached_data:
            return Response({"error": "OTP has expired or email is invalid"}, 
                          status=status.HTTP_400_BAD_REQUEST)
        
        # Verify OTP
        if cached_data["otp"] != otp:
            return Response({"error": "Invalid verification code"}, 
                          status=status.HTTP_400_BAD_REQUEST)
        
        # OTP verified, generate temp token for registration completion
        temp_token = str(uuid.uuid4())
        
        # Store validated data for registration completion
        cache.set(f"reg_{temp_token}", {
            'email': email,
            'username': cached_data["username"],
            'password': cached_data["password"],
            'auth_type': 'email'
        }, timeout=3600)
        
        # Clear the OTP from cache to prevent reuse
        cache.delete(f"otp_{email}")

        return Response({
            "message": "Email verified successfully. Please complete your registration",
            "temp_token": temp_token,
        }, status=status.HTTP_200_OK)

def assign_user_to_dynamic_group(user, role, city, institution=None, qualification=None):
    """Create and assign user to dynamic groups based on their role and location"""
    if role == "student" and institution and city:
        group_name = f"Students in {city} at {institution}"
    elif role == "tutor" and city:
        group_name = f"Tutors in {city}"
    elif role == "service provider" and city:
        group_name = f"Service Providers in {city}"
    elif role == "jobseeker" and city:
        group_name = f"Jobseekers in {city}"
    elif role == "hs student" and city:
        group_name = f"High School Students in {city}"
    else:
        group_name = f"{role.title()}s in {city}" 

    try:
        # Create Django auth group (for permissions)
        auth_group, created = Group.objects.get_or_create(name=group_name)
        user.groups.add(auth_group)
        
        # Create or get corresponding GroupChat
        group_chat, created = GroupChat.objects.get_or_create(
            name=group_name,
            city=city,
            institution=institution if role == "student" else "",
            defaults={
                'created_by': user,
                'is_dynamic': True,  # Mark as dynamic group
            }
        )
        
        # Add user to the group chat
        group_chat.members.add(user)
        
        # Create corresponding ChatRoom for WebSocket functionality
        chat_room, created = ChatRoom.objects.get_or_create(
            id=group_chat.id,
            defaults={'name': group_name}
        )
        chat_room.members.add(user)
        
        print(f"Successfully added user {user.username} to dynamic group: {group_name}")
        return group_chat
        
    except Exception as e:
        print(f"Error creating dynamic group for user {user.username}: {str(e)}")
        return None


class CompleteRegistrationView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        try:
            print("Incoming data:", request.data)

            temp_token = request.data.get("temp_token")
            if not temp_token:
                return Response({"error": "Missing registration token"}, status=status.HTTP_400_BAD_REQUEST)

            temp_data = cache.get(f"reg_{temp_token}")
            if not temp_data:
                return Response({"error": "Invalid or expired registration token"}, status=status.HTTP_400_BAD_REQUEST)

            email = temp_data['email']
            username = temp_data['username']
            password = request.data.get('password') or temp_data.get('password')

            if CustomUser.objects.filter(email=email).exists():
                return Response({'error': 'Email already registered.'}, status=status.HTTP_400_BAD_REQUEST)

            # Get roles - handle both string and list formats
            roles = request.data.get("roles", [])
            if isinstance(roles, str):
                try:
                    roles = json.loads(roles)  # Try to parse if it's a JSON string
                except json.JSONDecodeError:
                    roles = [roles]  # Treat as single role if not JSON

            if not roles:
                return Response({"error": "Missing roles"}, status=status.HTTP_400_BAD_REQUEST)

            valid_roles = ['student', 'tutor', 'hs student', 'service provider', 'jobseeker']
            invalid_roles = [role for role in roles if role not in valid_roles]
            
            if invalid_roles:
                return Response({"error": f"Invalid roles: {', '.join(invalid_roles)}"}, status=status.HTTP_400_BAD_REQUEST)
            user = CustomUser.objects.create_user(email=email, username=username, password=password, roles=roles)
            user.save()

            # Track created groups for response
            created_groups = []

            # Create profiles based on the selected roles
            for role in roles:
                city = request.data.get('city', '')
                qualification = request.data.get('qualification', '')
                institution = request.data.get('institution', '')

                if role == 'student':
                    StudentProfile.objects.create(
                        user=user,
                        city=city,
                        year_of_study=request.data.get('year_of_study'),
                        course=request.data.get('course', ''),
                        hobbies=request.data.get('hobbies', []),
                        qualification=qualification,
                        institution=institution
                    )
                    group = assign_user_to_dynamic_group(user, role, city, institution, qualification)
                    if group:
                        created_groups.append(group.name)

                elif role == 'tutor':
                    TutorProfile.objects.create(
                        user=user,
                        place=request.data.get('place', ''),
                        city=city,
                        phone_number=request.data.get('phone_number', ''),
                        hourly_rate=request.data.get('hourly_rate', 0),
                        cv=request.FILES.get('cv')
                    )
                    group = assign_user_to_dynamic_group(user, role, city)
                    if group:
                        created_groups.append(group.name)

                elif role == 'hs student':
                    HStudents.objects.create(
                        user=user,
                        schoolName=request.data.get('schoolName', ''),
                        studyLevel=request.data.get('studyLevel', ''),
                        city=city,
                        subjects=request.data.get('subjects', []),
                        hobbies=request.data.get('hobbies', [])
                    )
                    # Use schoolName as institution for hs students
                    school_name = request.data.get('schoolName', '')
                    group = assign_user_to_dynamic_group(user, role, city, school_name)
                    if group:
                        created_groups.append(group.name)

                elif role == 'service provider':
                    ServiceProvider.objects.create(
                        user=user,
                        company=request.data.get('company', ''),
                        about=request.data.get('about', ''),
                        city=city,
                        usageType=request.data.get('typeofservice', ''),
                        sectors=request.data.get('sectors', []),  # Fixed space issue
                        hobbies=request.data.get('hobbies', []),
                        serviceNeeds=request.data.get('serviceNeeds', [])
                    )
                    group = assign_user_to_dynamic_group(user, role, city)
                    if group:
                        created_groups.append(group.name)

                elif role == 'jobseeker':
                    JobSeeker.objects.create(
                        user=user,
                        cellnumber=request.data.get('cellnumber', ''),
                        status=request.data.get('status', []),
                        city=city,
                        usage=request.data.get('usage', []),
                        hobbies=request.data.get('hobbies', []),
                    )
                    group = assign_user_to_dynamic_group(user, role, city)
                    if group:
                        created_groups.append(group.name)

            refresh = RefreshToken.for_user(user)
            cache.delete(f"reg_{temp_token}")

            response_data = {
                "message": "Profile completed successfully",
                "user": UserSerializer(user).data,
                "groups_joined": created_groups,  # List of dynamic groups user was added to
                "token": {
                    "refresh": str(refresh),
                    "access": str(refresh.access_token),
                }
            }

            print(f"User {user.username} successfully registered and added to groups: {created_groups}")
            
            return Response(response_data, status=status.HTTP_200_OK)

        except Exception as e:
            import traceback
            traceback.print_exc()
            return Response({"error": f"Registration error: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class LoginView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        email = request.data.get("email")
        password = request.data.get("password")

        if not email or not password:
            return Response({"error": "Email and password are required"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            user = CustomUser.objects.get(email=email)
            authenticated_user = authenticate(username=user.username, password=password)

            if authenticated_user and authenticated_user.is_active:
                login(request, authenticated_user)
                refresh = RefreshToken.for_user(authenticated_user)

                return Response({
                    "message": "Login successful",
                    "user": UserSerializer(authenticated_user).data,
                    "role": user.roles,
                    "token": {
                        "refresh": str(refresh),
                        "access": str(refresh.access_token),
                    }
                }, status=status.HTTP_200_OK)

        except CustomUser.DoesNotExist:
            pass

        return Response({"error": "Invalid credentials"}, status=status.HTTP_401_UNAUTHORIZED)
    
class ForgotPasswordView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        email = request.data.get("email")
        if not email:
            return Response({"error": "Email is required."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            user = CustomUser.objects.get(email=email)
        except CustomUser.DoesNotExist:
            return Response({"error": "No user found with this email."}, status=status.HTTP_404_NOT_FOUND)

        # Generate UID and token
        uid = urlsafe_base64_encode(force_bytes(user.pk))
        token = default_token_generator.make_token(user)

        # Store in cache for faster validation
        cache_key = f"password_reset_{uid}"
        cache.set(cache_key, {
            'token': token,
            'email': user.email,
            'user_id': user.pk
        }, timeout=3600 * 24)  # Store for 24 hours

        # Construct reset URL
        reset_url = f"{settings.FRONTEND_URL}/resetpassword?uid={uid}&token={token}"

        # Email subject and message
        subject = "Reset Your Password"
        message = f"""
        Hello {user.username},
        
        You're receiving this email because you requested a password reset for your account.
        
        Please click the link below to reset your password:
        {reset_url}
        
        If you didn't request this, please ignore this email.
        
        Thanks,
        Your Ispani Team
        """

        # Send the email
        try:
            send_mail(
                subject=subject,
                message=message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[email],
                fail_silently=False,
            )
            return Response({"message": "Password reset link sent to your email."}, status=status.HTTP_200_OK)
        except Exception as e:
            return Response(
                {"error": f"Failed to send email: {str(e)}"}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class ResetPasswordView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        try:
            uidb64 = request.data.get("uid")
            token = request.data.get("token")
            new_password = request.data.get("new_password")
            confirm_password = request.data.get("confirm_password")

            if not all([uidb64, token, new_password, confirm_password]):
                return Response(
                    {"error": "Missing required fields."}, 
                    status=status.HTTP_400_BAD_REQUEST
                )

            if new_password != confirm_password:
                return Response(
                    {"error": "Passwords do not match."},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Decode uid first
            try:
                uid = force_str(urlsafe_base64_decode(uidb64))
                user = CustomUser.objects.get(pk=uid)
            except (TypeError, ValueError, OverflowError, CustomUser.DoesNotExist):
                return Response(
                    {"error": "Invalid user identifier."}, 
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Check cache first
            cache_key = f"password_reset_{uidb64}"
            cached_data = cache.get(cache_key)
            
            if cached_data and cached_data['token'] == token:
                # Cache is valid, proceed
                pass
            else:
                # Fall back to token generator if cache is missing
                if not default_token_generator.check_token(user, token):
                    return Response(
                        {"error": "Invalid or expired token."}, 
                        status=status.HTTP_400_BAD_REQUEST
                    )

            # All validations passed - reset password
            user.set_password(new_password)
            user.save()
            
            # Clear the reset token from cache
            cache.delete(cache_key)

            # Send confirmation email
            self._send_password_changed_email(user.email)

            return Response(
                {"message": "Password has been reset successfully."}, 
                status=status.HTTP_200_OK
            )

        except Exception as e:
            return Response(
                {"error": str(e)}, 
                status=status.HTTP_400_BAD_REQUEST
            )

    def _send_password_changed_email(self, email):
        """Helper method to send password changed confirmation email"""
        subject = "Your Password Has Been Changed"
        message = f"""
        <html>
            <body>
                <h2>Password Changed Successfully</h2>
                <p>This is a confirmation that the password for your account {email} has been changed.</p>
                <p>If you did not make this change, please contact our support team immediately.</p>
                <br>
                <p>Best regards,</p>
                <p>Your Ispani Team</p>
            </body>
        </html>
        """
        
        send_mail(
            subject=subject,
            message="",  # Empty message since we're using html_message
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[email],
            fail_silently=False,
            html_message=message,
        )

class LogoutView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        logout(request)
        return Response({"message": "Logout successful. Please delete the token on the client side."})
    

class DeleteAccountView(APIView):
    permission_classes = [IsAuthenticated]

    def delete(self, request):
        user = request.user

        try:
            # Delete related profiles if they exist
            StudentProfile.objects.filter(user=user).delete()
            TutorProfile.objects.filter(user=user).delete()
            HStudents.objects.filter(user=user).delete()
            ServiceProvider.objects.filter(user=user).delete()

            # cancel any future Stripe subscriptions or bookings here
            if user.stripe_customer_id:
                try:
                    # Cancel all subscriptions for the customer
                    subscriptions = stripe.Subscription.list(customer=user.stripe_customer_id)
                    for subscription in subscriptions.auto_paging_iter():
                        stripe.Subscription.delete(subscription.id)
                    
                    # delete the customer
                    stripe.Customer.delete(user.stripe_customer_id)
                except Exception as e:
                    print("Stripe cleanup error:", e)
                        
            user.delete()

            return Response({"message": "Account deleted successfully."}, status=status.HTTP_200_OK)

        except Exception as e:
            return Response({"error": f"Failed to delete account: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class SwitchRoleView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        new_role = request.data.get("role")

        if not new_role:
            return Response(
                {"error": "No role provided. Please specify the role to switch to."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        user = request.user

        # Check which roles this user actually has
        user_roles = []

        if hasattr(user, 'student_profile'):
            user_roles.append('student')
        if hasattr(user, 'tutor_profile'):
            user_roles.append('tutor')
        if hasattr(user, 'hstudents'):
            user_roles.append('jobseeker')
        if hasattr(user, 'serviceprovider'):
            user_roles.append('service_provider')

        # If the user has only one role, don't allow switching
        if len(user_roles) <= 1:
            return Response(
                {"error": "User only has one role. Cannot switch roles."},
                status=status.HTTP_403_FORBIDDEN,
            )

        # If the requested role is not among the user's roles, deny it
        if new_role not in user_roles:
            return Response(
                {
                    "error": f"You do not have the role '{new_role}'.",
                    "available_roles": user_roles,
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        # Optionally: store role in session 
        request.session["active_role"] = new_role

        # Or just return the active role in the response
        return Response(
            {
                "message": f"Switched to role '{new_role}' successfully.",
                "active_role": new_role,
                "available_roles": user_roles,
            },
            status=status.HTTP_200_OK,
        )
    
class SuggestedUsersView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            user = request.user
            user_city = getattr(user, 'city', None)

            # Exclude already connected or requested users
            connected_ids = set(ConnectionRequest.objects.filter(
                Q(from_user=user) | Q(to_user=user),
                status='accepted'
            ).values_list('from_user', 'to_user'))

            connected_ids = set(i for pair in connected_ids for i in pair if i != user.id)

            pending_ids = set(ConnectionRequest.objects.filter(
                from_user=user, status='pending'
            ).values_list('to_user', flat=True))

            exclude_ids = connected_ids.union(pending_ids, {user.id})

            candidates = CustomUser.objects.exclude(id__in=exclude_ids)

            # Scoring
            suggestions = []
            for candidate in candidates:
                score = 0
                if user_city and getattr(candidate, 'city', None) == user_city:
                    score += 1
                suggestions.append((score, candidate))

            suggestions.sort(key=lambda x: x[0], reverse=True)
            top_users = [user for score, user in suggestions if score > 0][:10]
            
            if not top_users:
                top_users = list(CustomUser.objects.exclude(id=user.id).order_by('?')[:10])

            serializer = UserSerializer(top_users, many=True, context={'request': request})
            return Response(serializer.data)
            
        except Exception as e:
            logger.error(f"Error in SuggestedUsersView: {str(e)}")
            return Response({'error': 'Failed to fetch suggested users'}, status=500)


class IncomingRequestsView(ListAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = ConnectionRequestSerializer

    def get_queryset(self):
        return ConnectionRequest.objects.filter(
            to_user=self.request.user, 
            status='pending'
        ).select_related('from_user', 'to_user')
    
    def get_serializer_context(self):
        context = super().get_serializer_context()
        context['request'] = self.request
        return context
    
    def list(self, request, *args, **kwargs):
        try:
            queryset = self.get_queryset()
            
            # Filter out any requests with null users
            valid_requests = []
            for req in queryset:
                if req.from_user and req.to_user:
                    valid_requests.append(req)
                else:
                    logger.warning(f"Found connection request with null user: {req.id}")
            
            serializer = self.get_serializer(valid_requests, many=True)
            return Response(serializer.data)
            
        except Exception as e:
            logger.error(f"Error in IncomingRequestsView: {str(e)}")
            return Response([], status=200)  # Return empty array instead of error


class OutgoingRequestsView(ListAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = ConnectionRequestSerializer

    def get_queryset(self):
        return ConnectionRequest.objects.filter(
            from_user=self.request.user, 
            status='pending'
        ).select_related('from_user', 'to_user')
    
    def get_serializer_context(self):
        context = super().get_serializer_context()
        context['request'] = self.request
        return context
    
    def list(self, request, *args, **kwargs):
        try:
            queryset = self.get_queryset()
            
            # Filter out any requests with null users
            valid_requests = []
            for req in queryset:
                if req.from_user and req.to_user:
                    valid_requests.append(req)
                else:
                    logger.warning(f"Found connection request with null user: {req.id}")
            
            serializer = self.get_serializer(valid_requests, many=True)
            return Response(serializer.data)
            
        except Exception as e:
            logger.error(f"Error in OutgoingRequestsView: {str(e)}")
            return Response([], status=200)  # Return empty array instead of error


class SendConnectionRequestView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        try:
            from_user = request.user
            to_user_id = request.data.get('to_user')

            if not to_user_id:
                return Response({'error': 'to_user is required.'}, status=400)
            
            try:
                to_user_id = int(to_user_id)
            except (ValueError, TypeError):
                return Response({'error': 'Invalid user ID format.'}, status=400)

            if from_user.id == to_user_id:
                return Response({'error': 'Cannot send request to yourself.'}, status=400)

            to_user = CustomUser.objects.filter(id=to_user_id).first()
            if not to_user:
                return Response({'error': 'User not found.'}, status=404)

            if ConnectionRequest.objects.filter(from_user=from_user, to_user=to_user).exists():
                return Response({'error': 'Request already sent.'}, status=400)

            connection = ConnectionRequest.objects.create(
                from_user=from_user,
                to_user=to_user,
                status='pending'
            )
            
            serializer = ConnectionRequestSerializer(connection, context={'request': request})
            return Response(serializer.data, status=201)
            
        except Exception as e:
            logger.error(f"Error in SendConnectionRequestView: {str(e)}")
            return Response({'error': 'Failed to send connection request'}, status=500)


class RespondToRequestView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        """Handle accepting/rejecting connection requests"""
        try:
            status_action = request.data.get('status')
            if status_action not in ['accepted', 'rejected']:
                return Response({'error': 'Invalid status. Must be "accepted" or "rejected"'}, status=400)

            req = ConnectionRequest.objects.filter(
                id=pk, 
                to_user=request.user, 
                status='pending'
            ).first()
            
            if not req:
                return Response({'error': 'Request not found or already handled'}, status=404)

            req.status = status_action
            req.save()
            
            return Response({'message': f'Request {status_action}'})
            
        except Exception as e:
            logger.error(f"Error in RespondToRequestView: {str(e)}")
            return Response({'error': 'Failed to respond to request'}, status=500)

    def delete(self, request, pk):
        """Handle cancelling connection requests"""
        try:
            # Find the request that the current user sent (from_user)
            req = ConnectionRequest.objects.filter(
                id=pk, 
                from_user=request.user, 
                status='pending'
            ).first()
            
            if not req:
                return Response({'error': 'Request not found or cannot be cancelled'}, status=404)

            # Delete the request (cancel it)
            req.delete()
            
            return Response({'message': 'Request cancelled successfully'})
            
        except Exception as e:
            logger.error(f"Error cancelling request: {str(e)}")
            return Response({'error': 'Failed to cancel request'}, status=500)


class ConnectionsListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            user = request.user

            connections = ConnectionRequest.objects.filter(
                Q(from_user=user) | Q(to_user=user),
                status='accepted'
            ).select_related('from_user', 'to_user')

            connected_users = []
            for conn in connections:
                other_user = conn.to_user if conn.from_user == user else conn.from_user
                if other_user:  # Ensure user exists
                    connected_users.append(other_user)

            serializer = UserSerializer(connected_users, many=True, context={'request': request})
            return Response(serializer.data)
            
        except Exception as e:
            logger.error(f"Error in ConnectionsListView: {str(e)}")
            return Response([], status=200)

# 6. Mutual Connections
class MutualConnectionsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, user_id):
        user = request.user
        target = CustomUser.objects.filter(id=user_id).first()
        if not target:
            return Response({'error': 'User not found'}, status=404)

        def get_connected_ids(u):
            connections = ConnectionRequest.objects.filter(
                Q(from_user=u) | Q(to_user=u),
                status='accepted'
            )
            ids = set()
            for conn in connections:
                ids.add(conn.to_user.id if conn.from_user == u else conn.from_user.id)
            return ids

        user_connections = get_connected_ids(user)
        target_connections = get_connected_ids(target)

        mutual_ids = user_connections.intersection(target_connections)
        mutual_users = CustomUser.objects.filter(id__in=mutual_ids)

        serializer = UserSerializer(mutual_users, many=True)
        return Response(serializer.data)
    
class ProfileView(APIView):
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        """Get current user's profile"""
        try:
            user = request.user
            serializer = UserSerializer(user, context={'request': request})
            return Response(serializer.data, status=status.HTTP_200_OK)
        except Exception as e:
            return Response(
                {'error': 'Failed to fetch profile', 'details': str(e)}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    def put(self, request):
        """Update current user's profile"""
        try:
            user = request.user
            serializer = UserSerializer(
                user, 
                data=request.data, 
                context={'request': request},
                partial=True  # Allow partial updates
            )
            
            if serializer.is_valid():
                serializer.save()
                return Response(serializer.data, status=status.HTTP_200_OK)
            else:
                return Response(
                    {'error': 'Validation failed', 'details': serializer.errors}, 
                    status=status.HTTP_400_BAD_REQUEST
                )
        except Exception as e:
            return Response(
                {'error': 'Failed to update profile', 'details': str(e)}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    def patch(self, request):
        """Partial update for current user's profile"""
        return self.put(request)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_user_by_id(request, user_id):
    """Get user profile by ID (for viewing other users)"""
    try:
        user = get_object_or_404(CustomUser, id=user_id)
        # Create a limited serializer for public profile viewing
        serializer = PublicUserSerializer(user, context={'request': request})
        return Response(serializer.data, status=status.HTTP_200_OK)
    except Exception as e:
        return Response(
            {'error': 'User not found', 'details': str(e)}, 
            status=status.HTTP_404_NOT_FOUND
        )


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def upload_profile_picture(request):
    """Upload profile picture separately"""
    try:
        user = request.user
        if 'profile_picture' not in request.FILES:
            return Response(
                {'error': 'No profile picture provided'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        user.profile_picture = request.FILES['profile_picture']
        user.save()
        
        serializer = UserSerializer(user, context={'request': request})
        return Response(
            {
                'message': 'Profile picture updated successfully',
                'user': serializer.data
            }, 
            status=status.HTTP_200_OK
        )
    except Exception as e:
        return Response(
            {'error': 'Failed to upload profile picture', 'details': str(e)}, 
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def remove_profile_picture(request):
    """Remove profile picture"""
    try:
        user = request.user
        if user.profile_picture:
            user.profile_picture.delete()
            user.profile_picture = None
            user.save()
            
        serializer = UserSerializer(user, context={'request': request})
        return Response(
            {
                'message': 'Profile picture removed successfully',
                'user': serializer.data
            }, 
            status=status.HTTP_200_OK
        )
    except Exception as e:
        return Response(
            {'error': 'Failed to remove profile picture', 'details': str(e)}, 
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )
