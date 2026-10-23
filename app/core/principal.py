"""Easy Auth principal parsing.

App Service built in authentication injects ``X-MS-CLIENT-PRINCIPAL``: base64 JSON with
``auth_typ``, ``claims`` (``[{typ, val}]``), ``name_typ`` and ``role_typ``. External requests
cannot set these headers, so they are trusted only behind Easy Auth (private endpoint plus
require authentication). Claim types may be mapped, so both short and URI forms are accepted.
"""

import base64
import binascii
import json
import logging
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from enum import StrEnum

logger = logging.getLogger(__name__)

PRINCIPAL_HEADER = "X-MS-CLIENT-PRINCIPAL"
PRINCIPAL_ID_HEADER = "X-MS-CLIENT-PRINCIPAL-ID"
PRINCIPAL_NAME_HEADER = "X-MS-CLIENT-PRINCIPAL-NAME"

ROLE_CLAIM_TYPES = frozenset(
    {"roles", "http://schemas.microsoft.com/ws/2008/06/identity/claims/role"}
)
OBJECT_ID_CLAIM_TYPES = ("oid", "http://schemas.microsoft.com/identity/claims/objectidentifier")
NAME_CLAIM_TYPES = ("name",)
EMAIL_CLAIM_TYPES = (
    "preferred_username",
    "email",
    "upn",
    "http://schemas.xmlsoap.org/ws/2005/05/identity/claims/emailaddress",
    "http://schemas.xmlsoap.org/ws/2005/05/identity/claims/upn",
)


class Role(StrEnum):
    """Entra app roles. Independent: no role implies another (decision D15)."""

    VIEWER = "viewer"
    REPORT_USER = "report_user"
    ADMIN = "admin"
    SUPPORT = "support"


@dataclass(frozen=True)
class Principal:
    object_id: str
    display_name: str
    email: str
    roles: frozenset[Role]
    idp: str

    def has_any(self, roles: Iterable[Role]) -> bool:
        return not self.roles.isdisjoint(roles)


def _first(claims: list[tuple[str, str]], types: Iterable[str]) -> str:
    wanted = tuple(types)
    for claim_type in wanted:
        for typ, val in claims:
            if typ == claim_type and val:
                return val
    return ""


def _roles(claims: list[tuple[str, str]], role_typ: object) -> frozenset[Role]:
    types = ROLE_CLAIM_TYPES | ({role_typ} if isinstance(role_typ, str) and role_typ else set())
    roles = set()
    for typ, val in claims:
        if typ not in types:
            continue
        try:
            roles.add(Role(val))
        except ValueError:
            logger.warning("Ignoring unknown role claim %r", val[:64])
    return frozenset(roles)


def parse_principal(headers: Mapping[str, str]) -> Principal | None:
    """Return the caller from Easy Auth headers, or None if absent or malformed."""
    raw = headers.get(PRINCIPAL_HEADER)
    if not raw:
        return None
    try:
        payload = json.loads(base64.b64decode(raw, validate=True))
    except (binascii.Error, ValueError):
        logger.warning("Malformed %s header", PRINCIPAL_HEADER)
        return None
    if not isinstance(payload, dict) or not isinstance(payload.get("claims"), list):
        logger.warning("Unexpected %s payload shape", PRINCIPAL_HEADER)
        return None

    claims = [
        (c["typ"], c["val"])
        for c in payload["claims"]
        if isinstance(c, dict) and isinstance(c.get("typ"), str) and isinstance(c.get("val"), str)
    ]
    object_id = _first(claims, OBJECT_ID_CLAIM_TYPES) or headers.get(PRINCIPAL_ID_HEADER, "")
    if not object_id:
        logger.warning("Principal has no object ID")
        return None
    fallback_name = headers.get(PRINCIPAL_NAME_HEADER, "")
    return Principal(
        object_id=object_id,
        display_name=_first(claims, NAME_CLAIM_TYPES) or fallback_name,
        email=_first(claims, EMAIL_CLAIM_TYPES) or fallback_name,
        roles=_roles(claims, payload.get("role_typ")),
        idp=str(payload.get("auth_typ") or ""),
    )


def encode_principal(object_id: str, name: str, email: str, roles: Iterable[str]) -> str:
    """Build a header value in the Easy Auth format. For the dev shim and tests only."""
    claims = [
        {"typ": "oid", "val": object_id},
        {"typ": "name", "val": name},
        {"typ": "preferred_username", "val": email},
        *({"typ": "roles", "val": role} for role in roles),
    ]
    payload = {"auth_typ": "aad", "claims": claims, "name_typ": "name", "role_typ": "roles"}
    return base64.b64encode(json.dumps(payload).encode()).decode()
