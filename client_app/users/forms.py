from django import forms
from django.contrib.auth.forms import UserCreationForm
from .models import CustomUser

class SignUpForm(UserCreationForm):
    abn = forms.CharField(max_length=15, required=True)
    company_name = forms.CharField(max_length=255, required=True)

    class Meta:
        model = CustomUser
        fields = ("username", "email", "abn", "company_name", "password1", "password2")
