from django.contrib.auth.models import AbstractUser
from django.db import models

ROLE_CHOICES = (
    ('Admin', 'Full Access'),
    ('Staff', 'View/Add/Update'),
    ('User', 'View Only'),
)

class CustomUser(AbstractUser):
    role = models.CharField(max_length=6, choices=ROLE_CHOICES, default='User')
    is_verified = models.BooleanField(default=False)
