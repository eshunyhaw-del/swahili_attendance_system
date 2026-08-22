from django import forms
from django.conf import settings
from django.contrib.auth.models import User, Group
from django.contrib.auth.forms import UserCreationForm
from .models import UserProfile, SupportTicket, Course, TAProfile, Level, Avatar
import uuid
import re


class StudentRegistrationForm(forms.ModelForm):
    full_name = forms.CharField(max_length=100, required=True, label="Full Name")
    email = forms.EmailField(required=True)
    student_id = forms.CharField(max_length=50, required=True, label="Student ID Number")
    level = forms.ChoiceField(choices=[('100', 'Level 100'), ('200', 'Level 200'), ('300', 'Level 300'), ('400', 'Level 400')], required=True)
    password = forms.CharField(
        min_length=8, required=True, label="Password",
        widget=forms.PasswordInput(attrs={'minlength': '8'})
    )
    password2 = forms.CharField(
        required=True, label="Confirm Password", widget=forms.PasswordInput
    )

    class Meta:
        model = User
        fields = ['email']

    def clean_email(self):
        email = self.cleaned_data.get('email')
        if not email or '@' not in email or '.' not in email:
            raise forms.ValidationError("Please enter a valid email address.")

        email_regex = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        if not re.match(email_regex, email):
            raise forms.ValidationError("Please enter a valid email address (e.g., name@example.com).")

        # New students may register only with an approved email domain. Our
        # verification codes are sent via Gmail and reliably reach only those
        # domains (see settings.ALLOWED_STUDENT_EMAIL_DOMAINS). This runs only on
        # new registrations, so existing accounts are unaffected.
        allowed = [d.lower() for d in getattr(
            settings, 'ALLOWED_STUDENT_EMAIL_DOMAINS', ['gmail.com', 'googlemail.com']
        )]
        domain = email.rsplit('@', 1)[-1].lower()
        if allowed and domain not in allowed:
            if allowed == ['gmail.com'] or set(allowed) <= {'gmail.com', 'googlemail.com'}:
                raise forms.ValidationError(
                    "Please register with a Gmail address (@gmail.com). Verification "
                    "codes are sent from Gmail and reliably reach only Gmail inboxes."
                )
            pretty = ' or '.join('@' + d for d in allowed)
            raise forms.ValidationError(
                f"Please register with a supported email address ({pretty}). "
                "Verification codes may not reach other providers."
            )

        existing = User.objects.filter(email__iexact=email).first()
        if existing:
            if existing.is_active:
                raise forms.ValidationError("An account with this email already exists. Please log in.")
            else:
                raise forms.ValidationError(
                    "This email is registered but not yet verified.",
                    code='email_unverified',
                )
        return email

    def clean_student_id(self):
        student_id = self.cleaned_data.get('student_id')
        existing = UserProfile.objects.filter(student_id_number=student_id).first()
        if existing:
            if existing.user.is_active:
                raise forms.ValidationError("This student ID is already registered. Please log in.")
            else:
                raise forms.ValidationError(
                    "This student ID is registered but not yet verified.",
                    code='student_id_unverified',
                )
        return student_id

    def clean_password(self):
        password = self.cleaned_data.get('password')
        student_id = self.cleaned_data.get('student_id')
        if password and student_id and password == student_id:
            raise forms.ValidationError("Password cannot be the same as your Student ID.")
        return password

    def clean_password2(self):
        password = self.cleaned_data.get('password')
        password2 = self.cleaned_data.get('password2')
        if password and password2 and password != password2:
            raise forms.ValidationError("Passwords do not match.")
        return password2

    def save(self, commit=True):
        student_id = self.cleaned_data['student_id']

        full_name = self.cleaned_data['full_name'].strip()
        parts = full_name.split(' ', 1)
        user = User(
            username=student_id,
            email=self.cleaned_data['email'],
            first_name=parts[0],
            last_name=parts[1] if len(parts) > 1 else '',
            is_active=False,
        )
        user.set_password(self.cleaned_data['password'])

        if commit:
            user.save()
            level_name = self.cleaned_data['level']
            level = Level.objects.get(name=level_name)

            UserProfile.objects.create(
                user=user,
                level=level,
                student_id_number=student_id,
                student_email=self.cleaned_data['email'],
                email_verified=True,
                must_change_password=False,
            )
        return user


class TARegistrationForm(UserCreationForm):
    full_name = forms.CharField(max_length=100, required=True, label="Full Name")
    email = forms.EmailField(required=True)
    assigned_levels = forms.ModelMultipleChoiceField(
        queryset=Level.objects.all(),
        widget=forms.CheckboxSelectMultiple,
        required=True,
        label="Select the levels you will be teaching"
    )

    class Meta:
        model = User
        fields = ['email', 'password1', 'password2']

    def clean_email(self):
        email = self.cleaned_data.get('email')
        if not email or '@' not in email or '.' not in email:
            raise forms.ValidationError("Please enter a valid email address.")

        email_regex = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        if not re.match(email_regex, email):
            raise forms.ValidationError("Please enter a valid email address.")

        existing = User.objects.filter(email__iexact=email).first()
        if existing:
            if existing.is_active:
                raise forms.ValidationError("An account with this email already exists.")
            else:
                raise forms.ValidationError(
                    "This email is registered but not yet verified. "
                    "Check your inbox for the verification code."
                )
        return email
    
    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data['email']

        # Split full name into first/last
        full_name = self.cleaned_data['full_name'].strip()
        parts = full_name.split(' ', 1)
        user.first_name = parts[0]
        user.last_name = parts[1] if len(parts) > 1 else ''

        # Auto-generate a unique username from the email prefix
        base = self.cleaned_data['email'].split('@')[0]
        username, n = base, 1
        while User.objects.filter(username=username).exists():
            username = f"{base}{n}"
            n += 1
        user.username = username

        user.is_staff = False
        user.is_active = False

        if commit:
            user.save()
            ta_group, _ = Group.objects.get_or_create(name="TA")
            user.groups.add(ta_group)
            profile = TAProfile.objects.create(
                user=user,
                is_approved=False
            )
            profile.assigned_levels.add(*self.cleaned_data['assigned_levels'])
        return user


class CourseRegistrationForm(forms.Form):
    courses = forms.ModelMultipleChoiceField(
        queryset=None,
        widget=forms.CheckboxSelectMultiple,
        required=True
    )

    def __init__(self, *args, **kwargs):
        level = kwargs.pop('level', None)
        semester = kwargs.pop('semester', None)
        super().__init__(*args, **kwargs)
        if level and semester:
            self.fields['courses'].queryset = Course.objects.filter(level=level, semester=semester)

    def clean_courses(self):
        courses = self.cleaned_data.get('courses', [])
        codes = {c.code for c in courses}
        if 'KISW 106A' in codes and 'KISW 106B' in codes:
            raise forms.ValidationError(
                "Please select only one KISW 106 group — either Monday (106A) or Thursday (106B), not both."
            )
        return courses


class SupportTicketForm(forms.ModelForm):
    class Meta:
        model = SupportTicket
        fields = ['subject', 'message']
        widgets = {
            'subject': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Enter subject'}),
            'message': forms.Textarea(attrs={'class': 'form-control', 'rows': 5, 'placeholder': 'Describe your issue...'}),
        }


# Admin Form for Approving TA
class TAApprovalForm(forms.ModelForm):
    class Meta:
        model = TAProfile
        fields = ['is_approved', 'approval_notes']
        widgets = {
            'approval_notes': forms.Textarea(attrs={'rows': 3, 'placeholder': 'Add any notes about this approval...'}),
        }


# ── Profile editing (all roles) ──────────────────────────────────────────────

class UserDetailsForm(forms.ModelForm):
    """Name + email, editable by every role. Email is the login key, so it must
    stay unique case-insensitively across all users."""

    class Meta:
        model = User
        fields = ['first_name', 'last_name', 'email']
        widgets = {
            'first_name': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'First name'}),
            'last_name': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'Last name'}),
            'email': forms.EmailInput(attrs={'class': 'form-input', 'placeholder': 'you@example.com'}),
        }

    def clean_email(self):
        email = (self.cleaned_data.get('email') or '').strip()
        if not email:
            raise forms.ValidationError("Email is required — it is how you sign in.")
        clash = User.objects.filter(email__iexact=email).exclude(pk=self.instance.pk)
        if clash.exists():
            raise forms.ValidationError("That email is already used by another account.")
        return email


class AvatarForm(forms.ModelForm):
    """Profile photo + phone, shared by every role via the Avatar model."""

    class Meta:
        model = Avatar
        fields = ['image', 'phone_number']
        widgets = {
            'image': forms.ClearableFileInput(attrs={'class': 'file-input', 'accept': 'image/*'}),
            'phone_number': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'e.g. 024 123 4567'}),
        }

    def clean_image(self):
        image = self.cleaned_data.get('image')
        # Only validate a freshly uploaded file (has content_type); an unchanged
        # existing image comes through as the stored FieldFile and is fine.
        if image and hasattr(image, 'content_type'):
            if image.size > 5 * 1024 * 1024:
                raise forms.ValidationError("Image must be 5 MB or smaller.")
            if not image.content_type.startswith('image/'):
                raise forms.ValidationError("Please upload an image file.")
        return image
