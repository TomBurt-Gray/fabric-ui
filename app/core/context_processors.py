from dataclasses import dataclass

from django.http import HttpRequest

from core.branding import get_branding
from core.principal import Principal, Role


@dataclass(frozen=True)
class NavItem:
    label: str
    url_name: str
    roles: frozenset[Role]


NAV_ITEMS = (
    NavItem("Home", "home", frozenset(Role)),
    NavItem("Support issues", "support:issue_list", frozenset({Role.SUPPORT})),
)


def visible_nav(principal: Principal | None, items: tuple[NavItem, ...] = NAV_ITEMS) -> list:
    if principal is None:
        return []
    return [item for item in items if principal.has_any(item.roles)]


def layout(request: HttpRequest) -> dict:
    principal = getattr(request, "principal", None)
    return {
        "branding": get_branding(),
        "principal": principal,
        "nav_items": visible_nav(principal),
    }
