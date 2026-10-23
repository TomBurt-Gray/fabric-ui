"""Per environment support settings from YAML. Validated at startup with clear errors."""

import functools
import re
import string
from dataclasses import dataclass
from pathlib import Path

import yaml
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured

DELIVERY_MODES = ("console", "graph")
PLACEHOLDERS = frozenset(
    {
        "app_name",
        "environment",
        "reference",
        "type_label",
        "subject",
        "requester_name",
        "requester_email",
        "created_utc",
        "impact_summary",
        "issue_url",
    }
)
SAMPLE_VALUES = dict.fromkeys(PLACEHOLDERS, "sample")

_PREFIX = re.compile(r"[A-Z]{2,6}")
_EMAIL = re.compile(r"[^@\s]+@[^@\s]+\.[^@\s]+")
_BASE_URL = re.compile(r"https?://[A-Za-z0-9.-]+(:\d+)?")


@dataclass(frozen=True)
class SupportSettings:
    reference_prefix: str
    delivery: str
    sender_mailbox: str
    recipient_mailbox: str
    app_base_url: str
    rate_limit_per_hour: int
    email_body: str

    def render_body(self, values: dict[str, str]) -> str:
        return self.email_body.format_map(values)


def template_errors(template: str) -> list[str]:
    """Only plain, known placeholders: no attribute access, indexing or format specs."""
    try:
        parsed = list(string.Formatter().parse(template))
    except ValueError as exc:
        return [f"email_body is not a valid template: {exc}"]
    errors = []
    for _, field, spec, conversion in parsed:
        if field is None:
            continue
        if field not in PLACEHOLDERS:
            errors.append(f"email_body uses unknown placeholder {{{field}}}")
        if spec or conversion:
            errors.append(f"email_body placeholder {{{field}}} must not use formatting")
    return errors


def load_support_config(path: Path) -> SupportSettings:
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        raise ImproperlyConfigured(f"Support config {path}: cannot read: {exc}") from exc
    if not isinstance(data, dict):
        raise ImproperlyConfigured(f"Support config {path}: expected a mapping")

    text = {
        k: data.get(k)
        for k in (
            "reference_prefix",
            "delivery",
            "sender_mailbox",
            "recipient_mailbox",
            "app_base_url",
            "email_body",
        )
    }
    errors = [
        f"'{k}' must be a non-empty string"
        for k, v in text.items()
        if not isinstance(v, str) or not v.strip()
    ]
    if errors:
        raise ImproperlyConfigured(f"Support config {path}: " + "; ".join(errors))

    if not _PREFIX.fullmatch(text["reference_prefix"]):
        errors.append("'reference_prefix' must be 2 to 6 capital letters")
    if text["delivery"] not in DELIVERY_MODES:
        errors.append(f"'delivery' must be one of {', '.join(DELIVERY_MODES)}")
    for key in ("sender_mailbox", "recipient_mailbox"):
        if not _EMAIL.fullmatch(text[key]):
            errors.append(f"'{key}' must be an email address")
    if not _BASE_URL.fullmatch(text["app_base_url"].rstrip("/")):
        errors.append("'app_base_url' must be an http(s) origin such as https://app.example.test")
    limit = data.get("rate_limit_per_hour")
    if not isinstance(limit, int) or isinstance(limit, bool) or not 1 <= limit <= 1000:
        errors.append("'rate_limit_per_hour' must be a whole number from 1 to 1000")
    errors += template_errors(text["email_body"])
    if errors:
        raise ImproperlyConfigured(f"Support config {path}: " + "; ".join(errors))

    config = SupportSettings(
        reference_prefix=text["reference_prefix"],
        delivery=text["delivery"],
        sender_mailbox=text["sender_mailbox"],
        recipient_mailbox=text["recipient_mailbox"],
        app_base_url=text["app_base_url"].rstrip("/"),
        rate_limit_per_hour=limit,
        email_body=text["email_body"],
    )
    config.render_body(SAMPLE_VALUES)  # Proves the template renders before any issue is raised.
    return config


@functools.cache
def get_support_config() -> SupportSettings:
    return load_support_config(Path(settings.SUPPORT_CONFIG))
