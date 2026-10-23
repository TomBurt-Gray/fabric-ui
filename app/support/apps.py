from django.apps import AppConfig


class SupportConfig(AppConfig):
    """Issue reporting, outbox and support email."""

    name = "support"

    def ready(self) -> None:
        from support import events  # noqa: F401  Registers the support audit events.
        from support.config import get_support_config

        get_support_config()  # Fail at startup, not on the first issue, if config is invalid.
