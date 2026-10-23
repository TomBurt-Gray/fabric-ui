"""Per environment audit settings from YAML. Validated at startup with clear errors."""

import functools
import re
from dataclasses import dataclass, field
from pathlib import Path

import yaml
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured

_HEADER_NAME = re.compile(r"[A-Za-z0-9-]{1,64}")
_FIELD_NAME = re.compile(r"[a-z][a-z0-9_]{0,63}")


@dataclass(frozen=True)
class AuditSettings:
    source_system: str
    environment: str
    capture_network: bool
    client_ip_header: str
    static_fields: dict[str, str] = field(default_factory=dict)


def load_audit_config(path: Path) -> AuditSettings:
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        raise ImproperlyConfigured(f"Audit config {path}: cannot read: {exc}") from exc
    if not isinstance(data, dict):
        raise ImproperlyConfigured(f"Audit config {path}: expected a mapping")

    errors = [
        f"'{name}' must be a non-empty string"
        for name in ("source_system", "environment", "client_ip_header")
        if not isinstance(data.get(name), str) or not data[name].strip()
    ]
    if not isinstance(data.get("capture_network"), bool):
        errors.append("'capture_network' must be true or false")
    header = data.get("client_ip_header")
    if isinstance(header, str) and not _HEADER_NAME.fullmatch(header):
        errors.append("'client_ip_header' must be an HTTP header name")
    static_fields = data.get("static_fields") or {}
    if not isinstance(static_fields, dict) or not all(
        isinstance(k, str) and _FIELD_NAME.fullmatch(k) and isinstance(v, str)
        for k, v in static_fields.items()
    ):
        errors.append("'static_fields' must map lower case names to strings")
    if errors:
        raise ImproperlyConfigured(f"Audit config {path}: " + "; ".join(errors))

    return AuditSettings(
        source_system=data["source_system"].strip(),
        environment=data["environment"].strip(),
        capture_network=data["capture_network"],
        client_ip_header=header,
        static_fields=dict(static_fields),
    )


@functools.cache
def get_audit_config() -> AuditSettings:
    return load_audit_config(Path(settings.AUDIT_CONFIG))
