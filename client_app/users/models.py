from django.db import models
from django.contrib.auth.models import AbstractUser

class CustomUser(AbstractUser):
    abn = models.CharField(max_length=15, blank=True, null=True, unique=True)
    company_name = models.CharField(max_length=255, blank=True, null=True)

    def __str__(self):
        return f"{self.username} ({self.company_name})"