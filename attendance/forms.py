from django import forms
from django.contrib.auth.models import User, Group
from django.contrib.auth.forms import UserCreationForm
from .models import UserProfile, SupportTicket, Course, TAProfile, Level
import uuid
import re


class StudentRegistrationForm(forms.ModelForm):
    email = forms.EmailField(required=True)
    student_id = forms.CharField(max_length=50, required=True, label="Student ID Number")
    level = forms.ChoiceField(choices=[('100', 'Level 100'), ('200', 'Level 200'), ('300', 'Level 300'), ('400', 'Level 400')], required=True)
    first_name = forms.CharField(max_length=30, required=True)
    last_name = forms.CharField(max_length=30, required=True)
    confirm_student_id = forms.CharField(max_length=50, required=True, label="Confirm Student ID", widget=forms.PasswordInput)
    
    class Meta:
        model = User
        fields = ['first_name', 'last_name', 'email']
    
    def clean_email(self):
        email = self.cleaned_data.get('email')
        # Basic email validation (accepts any valid email - Gmail, Yahoo, Outlook, UG, etc.)
        if not email or '@' not in email or '.' not in email:
            raise forms.ValidationError("Please enter a valid email address.")
        
        # Optional: Add regex for stricter validation
        email_regex = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        if not re.match(email_regex, email):
            raise forms.ValidationError("Please enter a valid email address (e.g., name@example.com).")
        
        return email
    
    def clean_student_id(self):
        student_id = self.cleaned_data.get('student_id')
        if UserProfile.objects.filter(student_id_number=student_id).exists():
            raise forms.ValidationError("This student ID is already registered")
        return student_id
    
    def clean_confirm_student_id(self):
        student_id = self.cleaned_data.get('student_id')
        confirm = self.cleaned_data.get('confirm_student_id')
        if student_id != confirm:
            raise forms.ValidationError("Student ID does not match")
        return confirm
    
    def save(self, commit=True):
        student_id = self.cleaned_data['student_id']
        
        user = User(
            username=student_id,
            email=self.cleaned_data['email'],
            first_name=self.cleaned_data['first_name'],
            last_name=self.cleaned_data['last_name'],
            is_active=True  # Changed to True - Account active immediately (no email verification needed)
        )
        user.set_password(student_id)
        
        if commit:
            user.save()
            level_name = self.cleaned_data['level']
            level = Level.objects.get(name=level_name)
            
            UserProfile.objects.create(
                user=user,
                level=level,
                student_id_number=student_id,
                student_email=self.cleaned_data['email'],
                email_verified=True,  # Changed to True - Auto-verified
                # email_verification_token removed since no verification needed
            )
        return user


class TARegistrationForm(UserCreationForm):
    email = forms.EmailField(required=True)
    phone_number = forms.CharField(max_length=15, required=True)
    assigned_levels = forms.ModelMultipleChoiceField(
        queryset=Level.objects.all(),
        widget=forms.CheckboxSelectMultiple,
        required=True,
        label="Select the levels you will be teaching"
    )
    first_name = forms.CharField(max_length=30, required=True)
    last_name = forms.CharField(max_length=30, required=True)
    
    class Meta:
        model = User
        fields = ['username', 'first_name', 'last_name', 'email', 'password1', 'password2']
    
    def clean_email(self):
        email = self.cleaned_data.get('email')
        # Basic email validation for TA as well
        if not email or '@' not in email or '.' not in email:
            raise forms.ValidationError("Please enter a valid email address.")
        
        email_regex = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        if not re.match(email_regex, email):
            raise forms.ValidationError("Please enter a valid email address.")
        
        return email
    
    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data['email']
        user.first_name = self.cleaned_data['first_name']
        user.last_name = self.cleaned_data['last_name']
        user.is_staff = False
        user.is_active = True  # TA can login but needs approval to generate codes

        if commit:
            user.save()
            ta_group, _ = Group.objects.get_or_create(name="TA")
            user.groups.add(ta_group)
            profile = TAProfile.objects.create(
                user=user,
                phone_number=self.cleaned_data['phone_number'],
                is_approved=False  # Requires admin approval
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
        