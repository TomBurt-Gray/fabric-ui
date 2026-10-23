import pytest
from django.db import DatabaseError, connection, transaction
from django.http import HttpRequest

from audit.models import AppendOnlyError, AuditEvent
from audit.service import record
from audit.tests.sample import SampleChange

pytestmark = pytest.mark.django_db


@pytest.fixture
def entry(audit_request: HttpRequest) -> AuditEvent:
    return record(audit_request, SampleChange(item="w", amount=1))


def test_saving_an_existing_row_fails(entry: AuditEvent) -> None:
    entry.message = "tampered"
    with pytest.raises(AppendOnlyError):
        entry.save()


def test_deleting_a_row_fails(entry: AuditEvent) -> None:
    with pytest.raises(AppendOnlyError):
        entry.delete()


def test_queryset_update_and_delete_fail(entry: AuditEvent) -> None:
    with pytest.raises(AppendOnlyError):
        AuditEvent.objects.update(message="tampered")
    with pytest.raises(AppendOnlyError):
        AuditEvent.objects.all().delete()
    with pytest.raises(AppendOnlyError):
        AuditEvent.objects.bulk_update([entry], ["message"])


@pytest.mark.parametrize(
    "sql",
    [
        "UPDATE audit_auditevent SET message = 'tampered'",
        "DELETE FROM audit_auditevent",
    ],
)
def test_raw_sql_is_blocked_by_the_database(entry: AuditEvent, sql: str) -> None:
    with pytest.raises(DatabaseError), transaction.atomic(), connection.cursor() as cursor:
        cursor.execute(sql)
    assert AuditEvent.objects.get().message == ""
