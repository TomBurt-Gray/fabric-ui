from dataclasses import dataclass
from io import StringIO
from pathlib import Path

import pytest
from django.core.exceptions import ImproperlyConfigured
from django.core.management import call_command

from audit import events
from audit.config import load_audit_config
from audit.events import AuditEventType, Category, register

VALID_CONFIG = """\
source_system: fabric-ui
environment: test
capture_network: true
client_ip_header: X-Forwarded-For
static_fields: {business_unit: Example}
"""


@pytest.fixture
def clean_registry(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(events, "_REGISTRY", dict(events._REGISTRY))


def test_catalogue_command_lists_access_denied() -> None:
    out = StringIO()
    call_command("audit_events", stdout=out)
    assert "auth.access_denied  category=security  v1  path: str" in out.getvalue()


def test_register_accepts_valid_event(clean_registry: None) -> None:
    @register
    @dataclass(frozen=True)
    class Valid(AuditEventType):
        event_type = "tests.valid"
        category = Category.DATA_ACCESS
        table: str

    assert events.registered_events()["tests.valid"] is Valid


def test_register_rejects_duplicates(clean_registry: None) -> None:
    @dataclass(frozen=True)
    class Duplicate(AuditEventType):
        event_type = "auth.access_denied"
        category = Category.SECURITY

    with pytest.raises(ValueError):
        register(Duplicate)


@pytest.mark.parametrize("name", ["", "nodot", "Upper.case", "a..b"])
def test_register_rejects_bad_names(clean_registry: None, name: str) -> None:
    cls = dataclass(frozen=True)(
        type("Bad", (AuditEventType,), {"event_type": name, "category": Category.CONFIG})
    )
    with pytest.raises(ValueError):
        register(cls)


def test_register_rejects_non_dataclass(clean_registry: None) -> None:
    class Plain(AuditEventType):
        event_type = "tests.plain"
        category = Category.CONFIG

    with pytest.raises(TypeError):
        register(Plain)


def test_repository_example_config_is_valid() -> None:
    config_dir = Path(__file__).resolve().parents[3] / "config"
    config = load_audit_config(config_dir / "audit.example.yaml")
    assert config.capture_network is True


def test_valid_config_loads(tmp_path: Path) -> None:
    path = tmp_path / "audit.yaml"
    path.write_text(VALID_CONFIG, encoding="utf-8")
    assert load_audit_config(path).static_fields == {"business_unit": "Example"}


@pytest.mark.parametrize(
    ("old", "new"),
    [
        ("capture_network: true", "capture_network: 'yes'"),
        ("client_ip_header: X-Forwarded-For", "client_ip_header: 'bad header!'"),
        ("source_system: fabric-ui", "source_system: ''"),
        ("{business_unit: Example}", "{BadName: Example}"),
        ("{business_unit: Example}", "{business_unit: 3}"),
    ],
)
def test_invalid_config_is_rejected(tmp_path: Path, old: str, new: str) -> None:
    path = tmp_path / "audit.yaml"
    path.write_text(VALID_CONFIG.replace(old, new), encoding="utf-8")
    with pytest.raises(ImproperlyConfigured):
        load_audit_config(path)
