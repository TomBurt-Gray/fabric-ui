from django.apps import AppConfig


class AuditConfig(AppConfig):
    """Business audit events and archive export."""

    name = "audit"

    def ready(self) -> None:
        from audit.config import get_audit_config

        get_audit_config()  # Fail at startup, not on first audited action, if config is invalid.
