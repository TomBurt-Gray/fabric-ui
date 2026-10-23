from django.core.management.base import BaseCommand

from support.delivery import send_due


class Command(BaseCommand):
    help = (
        "Retry due support issue deliveries. Safe to run concurrently (run by the scheduled job)."
    )

    def add_arguments(self, parser: object) -> None:
        parser.add_argument("--limit", type=int, default=50, help="Maximum deliveries per run.")

    def handle(self, *args: object, **options: object) -> None:
        counts = send_due(limit=options["limit"])
        self.stdout.write(
            f"due={counts['due']} sent={counts['sent']} not_sent={counts['not_sent']}"
        )
