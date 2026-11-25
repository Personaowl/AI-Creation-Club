from django.conf import settings
from django.db import models


class IssuedMemberPassword(models.Model):
    member = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, primary_key=True)
    nonce = models.CharField(max_length=64, editable=False)
