from django.contrib.auth.backends import ModelBackend
from django.contrib.auth.models import User
from django.db.models import Q


class StudentIDBackend(ModelBackend):
    """
    Authenticate using Student ID instead of username
    Allows students to login using their Student ID number
    """
    def authenticate(self, request, username=None, password=None, **kwargs):
        try:
            # Try to find user by username OR student_id_number
            user = User.objects.get(
                Q(username=username) | Q(userprofile__student_id_number=username)
            )
            if user.check_password(password):
                return user
        except User.DoesNotExist:
            return None
        return None