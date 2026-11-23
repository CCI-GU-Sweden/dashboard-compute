from decimal import Decimal, InvalidOperation
from django.core.management.base import BaseCommand, CommandError
from django.utils.dateparse import parse_datetime
from dashboard_compute.models import Rate


class Command(BaseCommand):
    help = "Add a source's effective rate; existing rates are never overwritten."

    def add_arguments(self, parser):
        parser.add_argument("source")
        parser.add_argument("effective_from", help="ISO timestamp with timezone")
        parser.add_argument("currency", help="Three-letter currency code")
        parser.add_argument("cpu", help="Cost per CPU core-hour")
        parser.add_argument("memory", help="Cost per RAM GiB-hour")
        parser.add_argument("--disk", help="Cost per disk GiB-hour")

    def handle(self, *args, **options):
        timestamp = parse_datetime(options["effective_from"])
        currency = options["currency"]
        if not timestamp or timestamp.utcoffset() is None or len(currency) != 3 or not currency.isascii() or not currency.isalpha():
            raise CommandError("Use a timezone-aware timestamp and three-letter currency")
        try:
            values = [Decimal(options[k]) if options[k] is not None else None for k in ("cpu", "memory", "disk")]
            if any(v is not None and (not v.is_finite() or v < 0 or v >= 10**8 or v.as_tuple().exponent < -4) for v in values):
                raise ValueError()
        except (InvalidOperation, ValueError):
            raise CommandError("Rates must be non-negative, under 100 million, and have at most four decimal places")
        Rate.objects.create(source=options["source"], effective_from=timestamp, currency=currency.upper(),
            cpu_per_core_hour=values[0], memory_per_gib_hour=values[1], disk_per_gib_hour=values[2])
        self.stdout.write("Rate added")
