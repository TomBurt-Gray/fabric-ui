"""Support issues and their delivery outbox.

The issue is saved before any delivery is attempted (FR07); each delivery is an outbox row
retried until sent (FR08, D06). Issue details stay in the client's database; only the
reference level summary is emailed (D22).
"""

from django.db import models
from django.utils import timezone


class IssueType(models.TextChoices):
    """Types users may choose; values match the support tracker. Problem and Change are
    support classifications applied during refinement, so users cannot pick them."""

    INCIDENT = "incident", "Incident"
    REQUEST = "request", "Service request"
    DEFECT = "defect", "Defect"
    ENHANCEMENT = "enhancement", "Enhancement"


IMPACT_FLAGS = {
    "processing_stopped": "Processing stopped",
    "deadline_at_risk": "Deadline or cut-off at risk",
    "integrity_in_doubt": "Data or control integrity in doubt",
    "regulatory_exposure": "Regulatory or client exposure",
}


class SupportIssue(models.Model):
    # Null until assigned from the primary key straight after insert, in the same transaction.
    reference = models.CharField(max_length=32, unique=True, null=True, blank=True)
    type = models.CharField(max_length=16, choices=IssueType.choices)
    subject = models.CharField(max_length=300)
    description = models.TextField()
    expected_behaviour = models.TextField(blank=True)
    actual_behaviour = models.TextField(blank=True)
    steps_to_reproduce = models.TextField(blank=True)
    workaround = models.TextField(blank=True)
    processing_stopped = models.BooleanField(default=False)
    deadline_at_risk = models.BooleanField(default=False)
    integrity_in_doubt = models.BooleanField(default=False)
    regulatory_exposure = models.BooleanField(default=False)
    page_url = models.CharField(max_length=2048, blank=True)
    filters = models.TextField(blank=True)
    page_correlation_id = models.CharField(max_length=128, blank=True)
    user_agent = models.CharField(max_length=512, blank=True)
    requester_object_id = models.CharField(max_length=64)
    requester_name = models.CharField(max_length=256, blank=True)
    requester_email = models.CharField(max_length=320, blank=True)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(
                fields=["requester_object_id", "created_at"], name="support_requester_idx"
            ),
        ]

    def __str__(self) -> str:
        return self.reference or f"issue {self.pk}"

    def impact_labels(self) -> list[str]:
        return [label for field, label in IMPACT_FLAGS.items() if getattr(self, field)]


class Delivery(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        SENT = "sent", "Sent"
        FAILED = "failed", "Failed"

    issue = models.ForeignKey(SupportIssue, on_delete=models.PROTECT, related_name="deliveries")
    channel = models.CharField(max_length=16, default="email")
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.PENDING)
    attempts = models.PositiveSmallIntegerField(default=0)
    next_attempt_at = models.DateTimeField(default=timezone.now)
    last_error = models.CharField(max_length=1000, blank=True)
    sent_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        indexes = [models.Index(fields=["status", "next_attempt_at"], name="support_due_idx")]

    def __str__(self) -> str:
        return f"{self.channel} {self.status} for {self.issue}"
