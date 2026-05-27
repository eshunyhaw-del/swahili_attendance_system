from django import forms
from django.contrib.auth.models import User
from .models import UserProfile, Level, ClassSession, Course


class StudentRegistrationForm(forms.ModelForm):
    password = forms.CharField(widget=forms.PasswordInput)
    level = forms.ModelChoiceField(queryset=Level.objects.all())

    class Meta:
        model = User
        fields = ['username', 'email', 'password']

    def save(self, commit=True):
        user = super().save(commit=False)
        user.set_password(self.cleaned_data['password'])
        if commit:
            user.save()
            UserProfile.objects.create(
                user=user,
                level=self.cleaned_data['level']
            )
        return user


class CodeSubmissionForm(forms.Form):
    code = forms.CharField(max_length=20, label="Enter Your Unique Code")


class CodeGenerationForm(forms.Form):
    class_session = forms.ModelChoiceField(queryset=ClassSession.objects.all())
    student = forms.ModelChoiceField(queryset=User.objects.filter(is_staff=False))


class BulkSessionForm(forms.Form):
    course = forms.ModelChoiceField(queryset=Course.objects.all())
    start_date = forms.DateField(
        widget=forms.DateInput(attrs={'type': 'date'}),
        label="First Class Date"
    )
    number_of_weeks = forms.IntegerField(
        min_value=1,
        max_value=20,
        initial=12,
        label="Number of Weeks"
    )