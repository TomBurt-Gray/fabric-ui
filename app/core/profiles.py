"""Keep the mutable user profile in step with the signed in principal."""

from datetime import timedelta

from django.db import IntegrityError, transaction
from django.utils import timezone

from core.models import UserProfile
from core.principal import Principal

REFRESH_AFTER = timedelta(minutes=15)


def record_profile(principal: Principal) -> None:
    """Create or update the profile; skip the write if nothing changed recently."""
    now = timezone.now()
    profile = UserProfile.objects.filter(object_id=principal.object_id).first()
    if profile is None:
        try:
            with transaction.atomic():
                UserProfile.objects.create(
                    object_id=principal.object_id,
                    display_name=principal.display_name,
                    email=principal.email,
                    last_seen=now,
                )
        except IntegrityError:
            pass  # A concurrent request created it first.
        return
    unchanged = (profile.display_name, profile.email) == (principal.display_name, principal.email)
    if unchanged and now - profile.last_seen < REFRESH_AFTER:
        return
    UserProfile.objects.filter(pk=profile.pk).update(
        display_name=principal.display_name, email=principal.email, last_seen=now
    )
