"""Create the audit table as append only.

Azure SQL: an append only ledger table, created with ``WITH (LEDGER = ON (APPEND_ONLY = ON))``
(Microsoft Learn, "Create and use append-only ledger tables"); requires ENABLE LEDGER.
Ledger cannot be turned off later. SQLite: triggers abort UPDATE and DELETE.
"""

import uuid

import django.db.models.functions.datetime
from django.db import migrations, models

LEDGER_OPTION = " WITH (LEDGER = ON (APPEND_ONLY = ON))"
SQLITE_TRIGGERS = (
    "CREATE TRIGGER audit_auditevent_no_update BEFORE UPDATE ON audit_auditevent "
    "BEGIN SELECT RAISE(ABORT, 'audit events are append only'); END",
    "CREATE TRIGGER audit_auditevent_no_delete BEFORE DELETE ON audit_auditevent "
    "BEGIN SELECT RAISE(ABORT, 'audit events are append only'); END",
)


def create_table(apps, schema_editor):
    model = apps.get_model("audit", "AuditEvent")
    vendor = schema_editor.connection.vendor
    if vendor == "microsoft":
        template = schema_editor.sql_create_table
        schema_editor.sql_create_table = template + LEDGER_OPTION
        try:
            schema_editor.create_model(model)
        finally:
            schema_editor.sql_create_table = template
        return
    schema_editor.create_model(model)
    if vendor == "sqlite":
        for statement in SQLITE_TRIGGERS:
            schema_editor.execute(statement)


def drop_table(apps, schema_editor):
    schema_editor.delete_model(apps.get_model("audit", "AuditEvent"))


class Migration(migrations.Migration):
    initial = True

    dependencies = []

    operations = [
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.CreateModel(
                    name="AuditEvent",
                    fields=[
                        (
                            "id",
                            models.BigAutoField(
                                auto_created=True, primary_key=True, serialize=False, verbose_name="ID"
                            ),
                        ),
                        ("event_id", models.UUIDField(default=uuid.uuid4, editable=False, unique=True)),
                        ("occurred_at", models.DateTimeField()),
                        (
                            "recorded_at",
                            models.DateTimeField(db_default=django.db.models.functions.datetime.Now()),
                        ),
                        ("event_type", models.CharField(max_length=64)),
                        ("category", models.CharField(max_length=32)),
                        ("outcome", models.CharField(max_length=16)),
                        ("schema_version", models.PositiveSmallIntegerField()),
                        ("source_system", models.CharField(max_length=64)),
                        ("environment", models.CharField(max_length=64)),
                        ("actor_object_id", models.CharField(blank=True, max_length=64)),
                        ("actor_roles", models.CharField(blank=True, max_length=256)),
                        ("target", models.CharField(blank=True, max_length=256)),
                        ("target_detail", models.CharField(blank=True, max_length=512)),
                        ("before", models.TextField(blank=True)),
                        ("after", models.TextField(blank=True)),
                        ("detail", models.TextField(blank=True)),
                        ("message", models.CharField(blank=True, max_length=512)),
                        ("correlation_id", models.CharField(max_length=128)),
                        ("client_ip", models.CharField(blank=True, max_length=45)),
                        ("user_agent", models.CharField(blank=True, max_length=512)),
                    ],
                    options={
                        "base_manager_name": "objects",
                        "indexes": [
                            models.Index(fields=["occurred_at"], name="audit_occurred_idx"),
                            models.Index(
                                fields=["actor_object_id", "occurred_at"], name="audit_actor_idx"
                            ),
                            models.Index(fields=["event_type", "occurred_at"], name="audit_type_idx"),
                        ],
                    },
                ),
            ],
            # The table is created below, where the historical model is available.
            database_operations=[],
        ),
        migrations.RunPython(create_table, drop_table),
    ]
