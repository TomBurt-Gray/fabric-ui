from django.apps import AppConfig


class CoreConfig(AppConfig):
    """Easy Auth principal, role mapping, correlation IDs, base layout."""

    name = "core"

    def ready(self) -> None:
        from core.branding import get_branding

        get_branding()  # Fail at startup, not on first request, if branding is invalid.
