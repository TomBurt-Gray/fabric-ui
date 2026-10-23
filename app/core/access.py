"""View access declarations. Every view must declare one; undeclared views are denied."""

from collections.abc import Callable
from dataclasses import dataclass

from core.principal import Role

_ACCESS_ATTR = "access_rule"


@dataclass(frozen=True)
class AccessRule:
    public: bool
    roles: frozenset[Role]


def _mark[View: Callable](view: View, rule: AccessRule) -> View:
    setattr(view, _ACCESS_ATTR, rule)
    return view


def require_roles[View: Callable](*roles: Role) -> Callable[[View], View]:
    """Allow callers holding at least one of ``roles``."""
    if not roles:
        raise ValueError("require_roles needs at least one role")
    rule = AccessRule(public=False, roles=frozenset(roles))
    return lambda view: _mark(view, rule)


any_role = require_roles(*Role)


def public[View: Callable](view: View) -> View:
    """No sign in needed. Only for endpoints that expose no data."""
    return _mark(view, AccessRule(public=True, roles=frozenset()))


def access_rule(view: Callable) -> AccessRule | None:
    return getattr(view, _ACCESS_ATTR, None)
