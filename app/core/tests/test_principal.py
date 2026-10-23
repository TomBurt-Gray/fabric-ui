import base64
import json

import pytest

from core.principal import Role, encode_principal, parse_principal


def _header(payload: object) -> dict[str, str]:
    raw = base64.b64encode(json.dumps(payload).encode()).decode()
    return {"X-MS-CLIENT-PRINCIPAL": raw}


def test_parses_encoded_principal() -> None:
    raw = encode_principal("oid-1", "Ada Example", "ada@example.test", ["viewer", "admin"])
    principal = parse_principal({"X-MS-CLIENT-PRINCIPAL": raw})
    assert principal is not None
    assert principal.object_id == "oid-1"
    assert principal.display_name == "Ada Example"
    assert principal.email == "ada@example.test"
    assert principal.roles == {Role.VIEWER, Role.ADMIN}
    assert principal.idp == "aad"


def test_accepts_mapped_uri_claim_types() -> None:
    role_uri = "http://schemas.microsoft.com/ws/2008/06/identity/claims/role"
    payload = {
        "auth_typ": "aad",
        "role_typ": role_uri,
        "claims": [
            {
                "typ": "http://schemas.microsoft.com/identity/claims/objectidentifier",
                "val": "oid-2",
            },
            {"typ": role_uri, "val": "report_user"},
        ],
    }
    principal = parse_principal(_header(payload))
    assert principal is not None
    assert principal.object_id == "oid-2"
    assert principal.roles == {Role.REPORT_USER}


def test_falls_back_to_principal_id_and_name_headers() -> None:
    headers = _header({"claims": [{"typ": "roles", "val": "viewer"}]})
    headers["X-MS-CLIENT-PRINCIPAL-ID"] = "oid-3"
    headers["X-MS-CLIENT-PRINCIPAL-NAME"] = "user@example.test"
    principal = parse_principal(headers)
    assert principal is not None
    assert principal.object_id == "oid-3"
    assert principal.display_name == "user@example.test"


def test_unknown_roles_are_dropped() -> None:
    raw = encode_principal("oid-4", "N", "e@example.test", ["viewer", "superuser"])
    principal = parse_principal({"X-MS-CLIENT-PRINCIPAL": raw})
    assert principal is not None
    assert principal.roles == {Role.VIEWER}


@pytest.mark.parametrize(
    "headers",
    [
        {},
        {"X-MS-CLIENT-PRINCIPAL": ""},
        {"X-MS-CLIENT-PRINCIPAL": "not base64!"},
        {"X-MS-CLIENT-PRINCIPAL": base64.b64encode(b"not json").decode()},
        _header(["a", "list"]),
        _header({"claims": "not a list"}),
        _header({"claims": [{"typ": "roles", "val": "viewer"}]}),  # no object ID
    ],
)
def test_missing_or_malformed_returns_none(headers: dict[str, str]) -> None:
    assert parse_principal(headers) is None


def test_has_any() -> None:
    raw = encode_principal("oid-5", "N", "e@example.test", ["support"])
    principal = parse_principal({"X-MS-CLIENT-PRINCIPAL": raw})
    assert principal is not None
    assert principal.has_any([Role.SUPPORT, Role.ADMIN])
    assert not principal.has_any([Role.VIEWER])
