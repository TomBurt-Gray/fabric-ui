"""Audit event types.

Each feature declares its events as frozen dataclasses that subclass ``AuditEventType`` and
are decorated with ``@register``. Fields are typed and become the event's JSON ``detail``.
Example::

    @register
    @dataclass(frozen=True)
    class ExportCreated(AuditEventType):
        event_type = "data.export_created"
        category = Category.DATA_EXPORT
        table: str
        row_count: int
"""

import dataclasses
import re
from dataclasses import dataclass
from enum import StrEnum
from typing import Any, ClassVar

_EVENT_TYPE = re.compile(r"[a-z][a-z0-9_]*(\.[a-z][a-z0-9_]*)+")


class Category(StrEnum):
    SECURITY = "security"
    DATA_ACCESS = "data_access"
    DATA_EXPORT = "data_export"
    SUPPORT = "support"
    CONFIG = "config"
    TRADE = "trade"


class Outcome(StrEnum):
    SUCCESS = "success"
    DENIED = "denied"
    FAILED = "failed"


@dataclass(frozen=True)
class AuditEventType:
    event_type: ClassVar[str]
    category: ClassVar[Category]
    schema_version: ClassVar[int] = 1

    def payload(self) -> dict[str, Any]:
        return dataclasses.asdict(self)


_REGISTRY: dict[str, type[AuditEventType]] = {}


def register[E: type[AuditEventType]](cls: E) -> E:
    """Add an event class to the catalogue. Names must be unique and dotted."""
    # The class itself must be decorated: an undecorated subclass inherits the base's
    # dataclass markers but its own fields would be silently left out of the payload.
    if not (issubclass(cls, AuditEventType) and "__dataclass_fields__" in vars(cls)):
        raise TypeError(f"{cls.__name__} must be a @dataclass subclassing AuditEventType")
    name = getattr(cls, "event_type", "")
    if not _EVENT_TYPE.fullmatch(name):
        raise ValueError(f"{cls.__name__}: event_type {name!r} must look like 'area.action'")
    if not isinstance(getattr(cls, "category", None), Category):
        raise TypeError(f"{cls.__name__}: category must be a Category")
    if name in _REGISTRY:
        raise ValueError(f"Audit event type {name!r} is already registered")
    _REGISTRY[name] = cls
    return cls


def registered_events() -> dict[str, type[AuditEventType]]:
    return dict(sorted(_REGISTRY.items()))


def is_registered(event: AuditEventType) -> bool:
    return _REGISTRY.get(getattr(event, "event_type", "")) is type(event)


@register
@dataclass(frozen=True)
class AccessDenied(AuditEventType):
    """A signed in user requested a page their roles do not allow."""

    event_type = "auth.access_denied"
    category = Category.SECURITY
    path: str
    required_roles: tuple[str, ...]
    reason: str
