"""Append only audit store.

On Azure SQL the table is an append only ledger table (see the migration); elsewhere the
model and database triggers refuse updates and deletes. Immutable rows hold only the
actor's Entra object ID (D12); network fields depend on the audit config switch (D18).
"""

import uuid

from django.db import models
from django.db.models.functions import Now


class AppendOnlyError(Exception):
    pass


class AuditEventQuerySet(models.QuerySet):
    def update(self, **kwargs: object) -> int:
        raise AppendOnlyError("Audit events cannot be updated.")

    def delete(self) -> tuple[int, dict[str, int]]:
        raise AppendOnlyError("Audit events cannot be deleted.")

    def bulk_update(self, objs: object, fields: object, batch_size: int | None = None) -> int:
        raise AppendOnlyError("Audit events cannot be updated.")


class AuditEvent(models.Model):
    event_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    occurred_at = models.DateTimeField()
    recorded_at = models.DateTimeField(db_default=Now())
    event_type = models.CharField(max_length=64)
    category = models.CharField(max_length=32)
    outcome = models.CharField(max_length=16)
    schema_version = models.PositiveSmallIntegerField()
    source_system = models.CharField(max_length=64)
    environment = models.CharField(max_length=64)
    actor_object_id = models.CharField(max_length=64, blank=True)
    actor_roles = models.CharField(max_length=256, blank=True)
    target = models.CharField(max_length=256, blank=True)
    target_detail = models.CharField(max_length=512, blank=True)
    # JSON as text (nvarchar(max) on Azure SQL), not the native json type, so the table
    # stays eligible for Fabric mirroring.
    before = models.TextField(blank=True)
    after = models.TextField(blank=True)
    detail = models.TextField(blank=True)
    message = models.CharField(max_length=512, blank=True)
    correlation_id = models.CharField(max_length=128)
    client_ip = models.CharField(max_length=45, blank=True)
    user_agent = models.CharField(max_length=512, blank=True)

    objects = AuditEventQuerySet.as_manager()

    class Meta:
        base_manager_name = "objects"
        indexes = [
            models.Index(fields=["occurred_at"], name="audit_occurred_idx"),
            models.Index(fields=["actor_object_id", "occurred_at"], name="audit_actor_idx"),
            models.Index(fields=["event_type", "occurred_at"], name="audit_type_idx"),
        ]

    def __str__(self) -> str:
        return f"{self.event_type} {self.event_id}"

    def save(self, *args: object, **kwargs: object) -> None:
        if not self._state.adding:
            raise AppendOnlyError("Audit events cannot be updated.")
        super().save(*args, **kwargs)

    def delete(self, *args: object, **kwargs: object) -> tuple[int, dict[str, int]]:
        raise AppendOnlyError("Audit events cannot be deleted.")
