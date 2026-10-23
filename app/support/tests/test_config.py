from pathlib import Path

import pytest
from django.core.exceptions import ImproperlyConfigured

from support.config import load_support_config

EXAMPLE = Path(__file__).resolve().parents[3] / "config" / "support.example.yaml"


def _load(tmp_path: Path, old: str, new: str):
    path = tmp_path / "support.yaml"
    path.write_text(EXAMPLE.read_text(encoding="utf-8").replace(old, new, 1), encoding="utf-8")
    return load_support_config(path)


def test_repository_example_is_valid() -> None:
    config = load_support_config(EXAMPLE)
    assert config.delivery == "console"
    assert config.reference_prefix == "FUI"


@pytest.mark.parametrize(
    ("old", "new"),
    [
        ("Reference: {reference}", "Reference: {description}"),  # Not an allowed placeholder.
        ("Reference: {reference}", "Reference: {reference.__class__}"),  # Attribute access.
        ("Reference: {reference}", "Reference: {reference:>40}"),  # Format spec.
        ("Reference: {reference}", "Reference: {reference"),  # Broken template.
        ("reference_prefix: FUI", "reference_prefix: fui"),
        ("delivery: console", "delivery: smtp"),
        ("recipient_mailbox: support@example.test", "recipient_mailbox: not-an-email"),
        ("app_base_url: http://localhost:8000", "app_base_url: localhost"),
        ("rate_limit_per_hour: 10", "rate_limit_per_hour: 0"),
    ],
)
def test_invalid_config_is_rejected(tmp_path: Path, old: str, new: str) -> None:
    with pytest.raises(ImproperlyConfigured):
        _load(tmp_path, old, new)
