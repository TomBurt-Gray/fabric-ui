import dataclasses

from django.core.management.base import BaseCommand

from audit.events import registered_events


def _type_name(annotation: object) -> str:
    return annotation.__name__ if isinstance(annotation, type) else str(annotation)


class Command(BaseCommand):
    help = "List registered audit event types with their category, version and fields."

    def handle(self, *args: object, **options: object) -> None:
        for name, cls in registered_events().items():
            fields = ", ".join(f"{f.name}: {_type_name(f.type)}" for f in dataclasses.fields(cls))
            self.stdout.write(f"{name}  category={cls.category}  v{cls.schema_version}  {fields}")
