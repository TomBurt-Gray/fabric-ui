import json
from collections.abc import Callable
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from support.models import SupportIssue
from support.payload import build_email, issue_payload

pytestmark = pytest.mark.django_db

SCHEMAS = Path(__file__).resolve().parents[1] / "schemas"
VALIDATOR = Draft202012Validator(json.loads((SCHEMAS / "support_issue.v1.json").read_text()))


@pytest.fixture
def issue(submit: Callable, django_capture_on_commit_callbacks: Callable) -> SupportIssue:
    with django_capture_on_commit_callbacks(execute=False):
        submit()
    return SupportIssue.objects.get()


def test_schema_is_valid_json_schema() -> None:
    Draft202012Validator.check_schema(VALIDATOR.schema)


def test_payload_matches_schema(issue: SupportIssue) -> None:
    VALIDATOR.validate(issue_payload(issue))


def test_sample_matches_schema() -> None:
    VALIDATOR.validate(json.loads((SCHEMAS / "support_issue.v1.sample.json").read_text()))


def test_email_carries_no_issue_content(issue: SupportIssue) -> None:
    email = build_email(issue)
    attachment = email.attachment.decode()
    for private in (issue.description, issue.steps_to_reproduce, "gold.fact_trades", "trade_date"):
        assert private not in email.body
        assert private not in attachment
        assert private not in email.subject


def test_email_shape(issue: SupportIssue) -> None:
    email = build_email(issue)
    assert email.subject == f"{issue.reference} Defect: Export button does nothing"
    assert email.attachment_name == f"{issue.reference}.support_issue.v1.json"
    assert f"Reference: {issue.reference}" in email.body
    assert "Impact reported: Deadline or cut-off at risk" in email.body
    assert f"/support/issues/{issue.reference}" in email.body
    payload = json.loads(email.attachment)
    assert payload["impact"]["deadline_at_risk"] is True
    assert payload["requester"] == {"name": "Test User", "email": "test.user@example.test"}
