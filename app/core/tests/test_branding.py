from collections.abc import Callable
from pathlib import Path

import pytest
from django.core.exceptions import ImproperlyConfigured
from django.test import Client

from core.branding import load_branding
from core.context_processors import NavItem, visible_nav
from core.principal import Principal, Role

VALID = """\
app_name: Test Portal
organisation: Test Organisation
logo: logo.svg
primary_colour: "#112233"
accent_colour: "#AABBCC"
"""


@pytest.fixture
def assets(tmp_path: Path) -> Path:
    (tmp_path / "logo.svg").write_text("<svg/>", encoding="utf-8")
    return tmp_path


def _load(assets: Path, text: str):
    path = assets / "branding.yaml"
    path.write_text(text, encoding="utf-8")
    return load_branding(path, assets)


def test_valid_branding_loads(assets: Path) -> None:
    branding = _load(assets, VALID)
    assert branding.app_name == "Test Portal"
    assert branding.primary_colour == "#112233"


@pytest.mark.parametrize(
    ("old", "new"),
    [
        ('"#112233"', '"red; } body { display: none"'),  # CSS injection attempt
        ("logo.svg", "missing.svg"),
        ("logo.svg", "../logo.svg"),
        ("logo.svg", "logo.gif"),
        ("app_name: Test Portal", "app_name: ''"),
    ],
)
def test_invalid_branding_is_rejected(assets: Path, old: str, new: str) -> None:
    with pytest.raises(ImproperlyConfigured):
        _load(assets, VALID.replace(old, new))


def test_non_mapping_is_rejected(assets: Path) -> None:
    with pytest.raises(ImproperlyConfigured):
        _load(assets, "- a list\n")


def test_repository_example_is_valid() -> None:
    config = Path(__file__).resolve().parents[3] / "config"
    load_branding(config / "branding.example.yaml", config / "branding")


def test_nav_is_filtered_by_role() -> None:
    items = (
        NavItem("Home", "home", frozenset(Role)),
        NavItem("Audit", "audit", frozenset({Role.ADMIN})),
    )
    viewer = Principal("oid", "V", "v@example.test", frozenset({Role.VIEWER}), "aad")
    admin = Principal("oid", "A", "a@example.test", frozenset({Role.ADMIN}), "aad")
    assert [i.label for i in visible_nav(viewer, items)] == ["Home"]
    assert [i.label for i in visible_nav(admin, items)] == ["Home", "Audit"]
    assert visible_nav(None, items) == []


@pytest.mark.django_db
def test_layout_renders_branding_and_accessibility_hooks(
    client: Client, signed_in: Callable
) -> None:
    html = client.get("/", **signed_in(Role.VIEWER)).content.decode()
    assert "Gold Data Portal" in html
    assert 'href="#main"' in html
    assert 'id="main"' in html
    assert "htmx-2.0.11.min.js" in html
    assert "Report an issue" in html
    assert "<style" not in html  # CSP: no inline styles


def test_brand_css_serves_colours(client: Client) -> None:
    css = client.get("/brand.css").content.decode()
    assert "--brand-primary: #1F3A5F" in css
