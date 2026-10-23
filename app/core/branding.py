"""Per environment branding from YAML. Validated at startup with clear errors."""

import functools
import re
from dataclasses import dataclass
from pathlib import Path

import yaml
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured

_HEX_COLOUR = re.compile(r"#[0-9A-Fa-f]{6}")
_LOGO_SUFFIXES = {".svg", ".png"}
_TEXT_FIELDS = ("app_name", "organisation", "logo", "primary_colour", "accent_colour")


@dataclass(frozen=True)
class Branding:
    app_name: str
    organisation: str
    logo: str
    primary_colour: str
    accent_colour: str


def load_branding(path: Path, assets_dir: Path) -> Branding:
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        raise ImproperlyConfigured(f"Branding config {path}: cannot read: {exc}") from exc
    if not isinstance(data, dict):
        raise ImproperlyConfigured(f"Branding config {path}: expected a mapping")

    errors = [
        f"'{field}' must be a non-empty string"
        for field in _TEXT_FIELDS
        if not isinstance(data.get(field), str) or not data[field].strip()
    ]
    if errors:
        raise ImproperlyConfigured(f"Branding config {path}: " + "; ".join(errors))

    for field in ("primary_colour", "accent_colour"):
        if not _HEX_COLOUR.fullmatch(data[field]):
            errors.append(f"'{field}' must be a hex colour like #1F3A5F")
    logo = data["logo"]
    if Path(logo).name != logo or Path(logo).suffix.lower() not in _LOGO_SUFFIXES:
        errors.append("'logo' must be a .svg or .png file name with no folders")
    elif not (assets_dir / logo).is_file():
        errors.append(f"'logo' file {logo} not found in {assets_dir}")
    if errors:
        raise ImproperlyConfigured(f"Branding config {path}: " + "; ".join(errors))

    return Branding(**{field: data[field].strip() for field in _TEXT_FIELDS})


@functools.cache
def get_branding() -> Branding:
    return load_branding(Path(settings.BRANDING_CONFIG), Path(settings.BRANDING_ASSETS_DIR))
