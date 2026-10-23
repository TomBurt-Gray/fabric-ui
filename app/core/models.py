from django.db import models


class UserProfile(models.Model):
    """Mutable display details for an Entra object ID.

    Immutable stores (audit, archives) hold only the object ID (decision D12), so GDPR
    erasure is handled here.
    """

    object_id = models.CharField(max_length=64, unique=True)
    display_name = models.CharField(max_length=256, blank=True)
    email = models.CharField(max_length=320, blank=True)
    last_seen = models.DateTimeField()

    def __str__(self) -> str:
        return self.object_id
