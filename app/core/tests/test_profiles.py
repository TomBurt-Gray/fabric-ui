from collections.abc import Callable
from datetime import timedelta

import pytest
from django.test import Client
from django.utils import timezone

from core import profiles
from core.models import UserProfile
from core.principal import Principal, Role

pytestmark = pytest.mark.django_db


def _principal(name: str = "Ada Example") -> Principal:
    return Principal("oid-p", name, "ada@example.test", frozenset({Role.VIEWER}), "aad")


def test_signed_in_request_creates_profile(client: Client, signed_in: Callable) -> None:
    client.get("/", **signed_in(Role.VIEWER, name="Test User"))
    profile = UserProfile.objects.get()
    assert profile.display_name == "Test User"
    assert profile.email == "test.user@example.test"


def test_unchanged_recent_profile_is_not_rewritten() -> None:
    profiles.record_profile(_principal())
    first_seen = UserProfile.objects.get().last_seen
    profiles.record_profile(_principal())
    assert UserProfile.objects.get().last_seen == first_seen


def test_changed_details_are_updated() -> None:
    profiles.record_profile(_principal())
    profiles.record_profile(_principal(name="Ada Renamed"))
    assert UserProfile.objects.get().display_name == "Ada Renamed"


def test_last_seen_refreshes_after_interval(monkeypatch: pytest.MonkeyPatch) -> None:
    profiles.record_profile(_principal())
    later = timezone.now() + profiles.REFRESH_AFTER + timedelta(seconds=1)
    monkeypatch.setattr(profiles.timezone, "now", lambda: later)
    profiles.record_profile(_principal())
    assert UserProfile.objects.get().last_seen == later
